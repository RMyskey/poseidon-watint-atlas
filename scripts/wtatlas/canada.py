"""Canada: ISC long-term drinking water advisories (First Nations public systems on reserve) and ECCC WSER reported wastewater systems.

ISC data file is the JSON that powers the "Map of lifted and active drinking water advisories" page.
WSER: ECCC Wastewater Systems Effluent Regulations Reported Data, Resaeu-Wser-identification.csv (Open Government Portal dataset 9e11e114-ef0d-4814-8d93-24af23716489).
Limits of scope: ISC covers First Nations on-reserve public systems only; provincial/municipal advisories are published by each province and are not aggregated here."""
import csv
import io
import json
import os

from .common import LAYERS, RAW, download, fetch, iso, log, now, num, save

ISC_URL = 'https://sac-isc.gc.ca/DAM/DAM-ISC-SAC/DAM-WTR/STAGING/texte-text/lTDWA_map_data_1572010201618_eng.txt'
WSER_URL = 'https://data-donnees.az.ec.gc.ca/api/file?path=%2Fsubstances%2Fplaninfrastruture%2Fwastewater-systems-effluent-regulations-reported-data%2FResaeu-Wser-identification.csv'
CA = os.path.join(RAW, 'ca')


def dwa():
    dest = os.path.join(CA, 'dwa.txt')
    try:
        download(ISC_URL, dest, timeout=120)
    except Exception as e:  # noqa: BLE001
        if not os.path.exists(dest):
            raise
        log('canada dwa: live download failed, using cached copy: %s' % e)
    d = json.load(open(dest, encoding='utf-8-sig'))
    comm = d['data']
    cur, comm_rows, lifted = [], [], 0
    for c in comm:
        lifted += len(c.get('LTDWALifted') or [])
        for a in c.get('LTDWACurrent') or []:
            la, lo = num(a.get('Lattitude') or a.get('Latitude')), num(a.get('Longitude'))
            cur.append({'id': a.get('AdvisoryID'), 'community': a.get('CommunityName'), 'system': (a.get('WaterSystemName') or '').strip(), 'region': a.get('RegionAcronym') or a.get('Region'), 'type': a.get('AdvisoryType'),
                        'set': a.get('DateSet'), 'ltdwa_since': a.get('DateLTDWASet'), 'expected': a.get('DateExpected') or '', 'pop': a.get('PopulatioEstimated'),
                        'measure': (a.get('CorrectiveMeasure') or '').strip().replace('\r\n', ' '), 'phase': a.get('LongPhase') or '', 'lat': la, 'lon': lo})
        comm_rows.append({'name': c.get('CommunityName'), 'prov': c.get('ProvinceAcronym'), 'pop': num(c.get('Population')), 'lat': num(c.get('Latitude')), 'lon': num(c.get('Longitude')), 'active': len(c.get('LTDWACurrent') or [])})
    save(LAYERS + '/ca_dwa.json', {'asof': (d.get('GenerateDate') or '')[:10] or iso(now())[:10], 'fetched': iso(now()), 'source': 'Indigenous Services Canada, long-term drinking water advisories on First Nations public water systems (map data file)',
                                   'url': 'https://isc.gc.ca/eng/1620925418298/1620925434679', 'communities': len(comm), 'active_ltdwa': len(cur), 'lifted_ltdwa_listed': lifted, 'active': cur,
                                   'communities_with_active': [c for c in comm_rows if c['active']],
                                   'note': 'Covers First Nations public systems on reserve only. Provincial and municipal advisories are published separately by each province and are not aggregated here.'}, compact=True)
    return {'communities': len(comm), 'active': len(cur), 'lifted': lifted, 'generated': d.get('GenerateDate')}


def wser():
    dest = os.path.join(CA, 'wser_identification.csv')
    try:
        download(WSER_URL, dest, timeout=180)
    except Exception as e:  # noqa: BLE001
        if not os.path.exists(dest):
            raise
        log('canada wser: live download failed, using cached copy: %s' % e)
    rows = list(csv.DictReader(open(dest, encoding='utf-8-sig', errors='replace')))
    keys = list(rows[0].keys())
    k = lambda frag: [x for x in keys if frag in x][0]
    kid, kown, knm, kcity, kprov, kvol, ktype, ktrt, klat, klon, kstat, kpt, kchl = (k('Facility Identification'), k('Owner Name'), k('System Name'), k('City'), k('Province (English)'),
        k('Average Daily Effluent Volume'), k('System Type (English)'), k('Treatment Types (English)'), k('Latitude'), k('Longitude'), k('System status (English)'), k('Type of Point (English)'), k('Chlorine Use Indicator (English)'))
    out, by_prov = [], {}
    for r in rows:
        la, lo = num(r.get(klat)), num(r.get(klon))
        if la is None or lo is None or not (41 < la < 84 and -142 < lo < -52):
            continue
        vol = num(r.get(kvol))
        out.append([round(lo, 4), round(la, 4), (r.get(knm) or '').strip(), (r.get(kown) or '').strip(), (r.get(kcity) or '').strip(), r.get(kprov), vol, r.get(ktype), (r.get(ktrt) or '').strip(), r.get(kstat), r.get(kpt), r.get(kchl)])
        P = by_prov.setdefault(r.get(kprov), {'n': 0, 'vol_m3d': 0.0})
        P['n'] += 1
        P['vol_m3d'] += vol or 0
    save(LAYERS + '/ca_wser.json', {'asof': '2026-09-28', 'fetched': iso(now()), 'source': 'Environment and Climate Change Canada, Wastewater Systems Effluent Regulations (WSER) Reported Data: system identification',
                                    'url': 'https://open.canada.ca/data/en/dataset/9e11e114-ef0d-4814-8d93-24af23716489', 'systems': len(rows), 'with_coords': len(out), 'by_province': by_prov,
                                    'cols': ['lon', 'lat', 'system', 'owner', 'city', 'province', 'avg_daily_effluent_m3', 'system_type', 'treatment', 'status', 'point_type', 'chlorine_use'], 'rows': out,
                                    'note': 'Open Government Portal record last modified 2026-09-28. Systems that discharge 100 m3/day or more of effluent are regulated under WSER; coordinates are final discharge points.'}, compact=True)
    return {'systems': len(rows), 'with_coords': len(out)}
