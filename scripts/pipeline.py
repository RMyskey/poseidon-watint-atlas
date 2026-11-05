#!/usr/bin/env python3
"""Poseidon NARINT / WATINT atlas data pipeline.

  python3 scripts/pipeline.py                  # run every feed that is due, then rebuild all outputs
  python3 scripts/pipeline.py --force          # run every feed now regardless of cadence
  python3 scripts/pipeline.py --only gdacs,usdm  # run selected feeds (implies --force for them)
  python3 scripts/pipeline.py --build-only     # no network: rebuild meta/sources/flow/findings/cop and assets/js/data.js

Curated inputs: data/source/ (reference.json, sources.json, cop_snapshot.json, supply figures, Aqueduct table).
Generated:      data/layers/*, data/{meta,sources,flow,findings,updates,review}.json, assets/js/data.js
Rules: feeds never edit data/source/. A failed feed keeps its previous layer and is marked stale in data/meta.json.
Items that need an analyst (limit changes, dataset releases) go to data/review.json.
Env: WT_USER_AGENT (optional contact string for polite fetching)"""
import argparse
import datetime as dt
import os
import re
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtatlas import build as B  # noqa: E402
from wtatlas import (boundaries, canada, datacenters, epa, groundwater, hazards, igrac, mexico, news, rrc, siting, watch, wqp)  # noqa: E402
from wtatlas.common import DATA, STATE, LAYERS, iso, load, log, now, parse_iso, save  # noqa: E402

H = 24
FEEDS = {
    'gdacs': {'label': 'GDACS drought/flood/cyclone events', 'cadence': 'daily', 'url': 'https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH', 'out': ['gdacs.json']},
    'quakes': {'label': 'USGS earthquakes (global M4.5+, North America M2.5+)', 'cadence': 'daily', 'url': 'https://earthquake.usgs.gov/fdsnws/event/1/query', 'out': ['quakes.json']},
    'gdelt': {'label': 'GDELT DOC 2.0 news alerts', 'cadence': 'daily', 'url': 'https://api.gdeltproject.org/api/v2/doc/doc', 'out': []},
    'gnews': {'label': 'Google News RSS alerts', 'cadence': 'daily', 'url': 'https://news.google.com/rss', 'out': []},
    'usdm': {'label': 'US Drought Monitor weekly map', 'cadence': 'weekly', 'url': 'https://droughtmonitor.unl.edu/', 'out': ['usdm.geojson']},
    'datacenters': {'label': 'FracTracker data center register', 'cadence': 'weekly', 'url': 'https://www.fractracker.org/', 'out': ['datacenters.json']},
    'isc_dwa': {'label': 'ISC First Nations drinking water advisories', 'cadence': 'weekly', 'url': 'https://isc.gc.ca/eng/1620925418298/1620925434679', 'out': ['ca_dwa.json']},
    'wser': {'label': 'ECCC WSER wastewater systems', 'cadence': 'monthly', 'url': 'https://open.canada.ca/data/en/dataset/9e11e114-ef0d-4814-8d93-24af23716489', 'out': ['ca_wser.json']},
    'rrc': {'label': 'Texas RRC wells and injection/disposal (ArcGIS REST)', 'cadence': 'monthly', 'url': 'https://gis.rrc.texas.gov/server/rest/services/rrc_public/RRC_Public_Viewer_Srvs/MapServer', 'out': ['tx_wells_grid.json', 'tx_swd.json']},
    'echo_sdwa': {'label': 'EPA ECHO / SDWIS public water systems', 'cadence': 'monthly', 'url': 'https://echo.epa.gov/tools/web-services/facility-search-drinking-water', 'out': ['sdwa_state.json', 'sdwa_county.json']},
    'echo_npdes': {'label': 'EPA ECHO / ICIS-NPDES major dischargers', 'cadence': 'monthly', 'url': 'https://echo.epa.gov/tools/web-services/facility-search-water', 'out': ['npdes_majors.json']},
    'wqp': {'label': 'Water Quality Portal groundwater aggregates (county, HUC8)', 'cadence': 'monthly', 'url': 'https://www.waterqualitydata.us/', 'out': ['wqp_county.json', 'wqp_huc8.json', 'wqp_top_sites.json']},
    'igrac': {'label': 'IGRAC GGMN global monitoring registry (WFS)', 'cadence': 'monthly', 'url': 'https://ggis.un-igrac.org/', 'out': ['ggmn_global.json']},
    'conagua': {'label': 'CONAGUA datos abiertos (Mexico)', 'cadence': 'monthly', 'url': 'https://sinav30.conagua.gob.mx:8080/docs/DatosAbiertos/', 'out': ['mx_aquifers.geojson']},
    'pwdb': {'label': 'USGS Produced Waters Geochemical Database', 'cadence': 'annual', 'url': 'https://doi.org/10.5066/P9DSRCZJ', 'out': ['pwdb_basins.json']},
    'nbga': {'label': 'USGS National Brackish Groundwater Assessment database', 'cadence': 'annual', 'url': 'https://doi.org/10.5066/F72F7KK1', 'out': ['nbga_grid.json']},
    'boundaries': {'label': 'Census county/state boundaries', 'cadence': 'annual', 'url': 'https://www2.census.gov/geo/tiger/GENZ2023/', 'out': ['us_counties.geojson']},
    'limits_watch': {'label': 'Watch: PFAS limits (Federal Register) and USGS dataset releases', 'cadence': 'weekly', 'url': 'https://www.federalregister.gov/', 'out': []},
    'siting': {'label': 'DERIVED: Texas data-center siting model and logistics', 'cadence': 'derived', 'url': '', 'out': ['siting_tx.json', 'logistics_tx.json']},
}
INPUTS_OF_SITING = {'rrc', 'nbga', 'pwdb', 'usdm', 'datacenters', 'quakes', 'echo_npdes'}
DUE_HOURS = {'daily': 20, 'weekly': 6.5 * 24, 'monthly': 27 * 24, 'annual': 360 * 24, 'derived': 10 ** 9}
ORDER = list(FEEDS)
NEWS_KEEP_DAYS = 120


def due(fm, name, force):
    if force:
        return True
    f = FEEDS[name]
    if f['cadence'] == 'derived':
        return False
    last = parse_iso((fm.get(name) or {}).get('last_success'))
    return last is None or (now() - last).total_seconds() / 3600 >= DUE_HOURS[f['cadence']]


def norm_title(t):
    return re.sub(r'[^a-z0-9]+', ' ', (t or '').lower()).strip()[:90]


def merge_updates(old, new):
    by_id, titles, out = {}, set(), []
    for it in new + old:
        if it['id'] in by_id or (it.get('feed') in ('gdelt', 'gnews') and news.NOISE.search(it.get('title', ''))):
            continue
        nt = norm_title(it['title'])
        if it.get('feed') in ('gdelt', 'gnews') and nt in titles:
            continue
        by_id[it['id']] = it
        titles.add(nt)
        out.append(it)
    keep = []
    for it in out:
        d = parse_iso(it.get('date'))
        if d is None or (now() - d).days <= NEWS_KEEP_DAYS:
            keep.append(it)
    keep.sort(key=lambda x: x.get('date') or '', reverse=True)
    return keep[:800]


def merge_review(old, new):
    by = {r['id']: r for r in old}
    for r in new:
        r.setdefault('created', iso(now()))
        r.setdefault('status', 'open')
        if r['id'] not in by:
            by[r['id']] = r
    lim = now() - dt.timedelta(days=365)
    items = [r for r in by.values() if (parse_iso(r.get('created')) or now()) >= lim]
    items.sort(key=lambda r: r.get('created') or '', reverse=True)
    return items


def hazard_items(gd, qk):
    """Intel items derived from the hazard feeds (not news): GDACS Orange/Red and induced-seismicity-region quakes."""
    out = []
    for e in (gd or {}).get('events', []):
        if e.get('alert') in ('Orange', 'Red') and e.get('type') in ('DR', 'FL', 'TC'):
            out.append({'id': 'gdacs-' + str(e['id']), 'feed': 'gdacs', 'date': (e.get('from') or '')[:10] + 'T00:00:00Z' if e.get('from') else None, 'title': 'GDACS %s alert: %s (%s)' % (e['alert'], e.get('name'), e.get('country')),
                        'url': e.get('url'), 'source': 'GDACS', 'category': 'hazard', 'regions': []})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--only', default='')
    ap.add_argument('--build-only', action='store_true')
    ap.add_argument('--news-window', default='2d', help='GDELT timespan / Google News when: (e.g. 2d, 7d)')
    a = ap.parse_args()
    os.makedirs(STATE, exist_ok=True)

    B.validate(load(DATA + '/source/reference.json'), load(DATA + '/source/sources.json'))
    old_meta = load(DATA + '/meta.json', {}) or {}
    fm = {k: dict((old_meta.get('feeds') or {}).get(k, {})) for k in FEEDS}
    for k, f in FEEDS.items():
        fm[k].update({'label': f['label'], 'cadence': f['cadence'], 'url': f['url'], 'outputs': f['out']})
    if a.build_only:
        B.build(feed_meta=fm)
        log('build-only: outputs regenerated')
        return 0

    only = [x.strip() for x in a.only.split(',') if x.strip()]
    bad = [x for x in only if x not in FEEDS]
    if bad:
        log('unknown feeds: %s (known: %s)' % (', '.join(bad), ', '.join(FEEDS)))
        return 2
    run = [k for k in ORDER if (k in only if only else due(fm, k, a.force))]
    for k in FEEDS:
        if k not in run:
            fm[k]['status_note'] = 'not due' if not only else 'not selected'
    upd = load(DATA + '/updates.json', {'items': []}) or {'items': []}
    rev = load(DATA + '/review.json', {'items': []}) or {'items': []}
    new_items, new_reviews = [], []
    ran_ok = set()

    def record(k, status, items=0, message='', extra=None):
        fm[k].update({'status': status, 'last_attempt': iso(now()), 'items': items, 'message': message[:400]})
        fm[k].pop('status_note', None)
        if status in ('ok', 'partial'):
            fm[k]['last_success'] = iso(now())
            ran_ok.add(k)
        elif os.path.exists(LAYERS) and all(os.path.exists(os.path.join(LAYERS, o)) for o in FEEDS[k]['out']) and FEEDS[k]['out']:
            fm[k]['stale'] = True
            fm[k]['message'] = ('Showing previous data. ' + fm[k]['message'])[:400]
        if extra is not None:
            fm[k]['detail'] = extra
        log('%-12s %-10s items=%s %s' % (k, status, items, message[:160]))

    simple = {'gdacs': (hazards.gdacs, lambda r: ('ok', len(r.get('events', [])) if isinstance(r, dict) else len(r), 'GDACS events in 21 days')),
              'quakes': (hazards.quakes, lambda r: ('ok', r['recent'], '%(recent)d global M4.5+ in 30 d; %(na_events)d North America M2.5+ in 5 y' % r)),
              'usdm': (hazards.usdm, lambda r: ('ok', r['classes'], 'map date %s' % r['map_date'])),
              'datacenters': (datacenters.run, lambda r: ('ok', r['records'], '%d records, %d with MW' % (r['records'], r.get('with_mw', 0)))),
              'isc_dwa': (canada.dwa, lambda r: ('ok', r['active'], '%d communities, %d active advisories' % (r['communities'], r['active']))),
              'wser': (canada.wser, lambda r: ('ok', r['systems'], '%d systems, %d with coordinates' % (r['systems'], r['with_coords']))),
              'rrc': (rrc.run, lambda r: ('ok', r['wells'], '%d wells, %d injection/disposal, %d commercial disposal' % (r['wells'], r['injection_disposal'], r['commercial_disposal']))),
              'echo_sdwa': (epa.sdwa, lambda r: (('partial' if r['errors'] else 'ok'), r['systems'], '%d systems (%d CWS), %d states, %d state errors' % (r['systems'], r['cws'], r['states'], r['errors']))),
              'echo_npdes': (epa.npdes, lambda r: (('partial' if r['errors'] else 'ok'), r['facilities'], '%d major permittees, %d state errors' % (r['facilities'], r['errors']))),
              'wqp': (wqp.run, lambda r: (('partial' if r['errors'] else 'ok'), sum(v.get('sites', 0) for v in r['summary'].values()), '%d state/parameter pulls failed' % r['errors'])),
              'igrac': (igrac.run, lambda r: ('ok', r, '%d GGMN points' % r)),
              'pwdb': (groundwater.pwdb, lambda r: ('ok', r['records'], '%d records, %d basins' % (r['records'], r['basins']))),
              'nbga': (groundwater.nbga, lambda r: ('ok', r['samples'], '%d TDS samples' % r['samples'])),
              'boundaries': (boundaries.run, lambda r: ('ok', 1, 'boundaries rebuilt'))}
    for k in run:
        try:
            if k in simple:
                fn, rep = simple[k]
                r = fn()
                st, n, msg = rep(r)
                record(k, st, n, msg)
            elif k == 'conagua':
                r = mexico.run()
                bad = [x for x, v in (r or {}).items() if isinstance(v, dict) and v.get('error')]
                record(k, 'partial' if bad else 'ok', len(r or {}), 'CONAGUA blocks automated downloads from some networks; local raw copies were used where the live fetch failed' + ((' (' + ', '.join(bad) + ')') if bad else ''))
            elif k == 'gdelt':
                its, n, errs = news.gdelt(timespan=a.news_window)
                new_items += its
                record(k, ('partial' if errs else 'ok') if n else 'error', len(its), '%d/%d queries ok; %s' % (n, len(news.GDELT_TOPICS), '; '.join(sorted(set(errs))[:2])))
            elif k == 'gnews':
                its, n, errs = news.gnews(when=a.news_window)
                new_items += its
                record(k, 'ok' if n else 'error', len(its), '%d queries; %s' % (n, '; '.join(errs[:3])))
            elif k == 'limits_watch':
                wst = load(STATE + '/watch.json', {}) or {}
                rv, wst = watch.run(wst)
                save(STATE + '/watch.json', wst)
                new_reviews += rv
                record(k, 'ok', len(rv), '%d review items' % len(rv))
            elif k == 'siting':
                pass
        except Exception as e:
            traceback.print_exc()
            record(k, 'error', 0, '%s: %s' % (type(e).__name__, e))
    # derived siting runs when forced/selected, or after any of its inputs refreshed, or when outputs are missing
    need = ('siting' in only) or (not only and a.force) or bool(ran_ok & INPUTS_OF_SITING) or not os.path.exists(LAYERS + '/siting_tx.json')
    if need and not (only and 'siting' not in only):
        try:
            r = siting.run()
            record('siting', 'ok', r['cells'], 'Longview cell rank %d of %d; %d Texas data centers in logistics' % (r['longview_rank'], r['cells'], r['tx_dcs']))
        except Exception as e:
            traceback.print_exc()
            record('siting', 'error', 0, '%s: %s' % (type(e).__name__, e))
    # hazard-derived intel items
    gd, qk = load(LAYERS + '/gdacs.json'), load(LAYERS + '/quakes.json')
    new_items += hazard_items(gd, qk)
    upd['items'] = merge_updates(upd.get('items', []), new_items)
    upd['generated_at'] = iso(now())
    rev['items'] = merge_review(rev.get('items', []), new_reviews)
    rev['generated_at'] = iso(now())
    save(DATA + '/updates.json', upd)
    save(DATA + '/review.json', rev)
    B.build(feed_meta=fm)
    log('done: %d updates, %d review items' % (len(upd['items']), len(rev['items'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
