"""Hazard and drought feeds: GDACS, USGS earthquakes (global recent + North America 5-year), US Drought Monitor."""
import datetime as dt
import io
import json
import re
import zipfile

from .common import BROWSER_UA, LAYERS, fetch, fetch_json, iso, log, now, save

GDACS = 'https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH'
USGS = 'https://earthquake.usgs.gov/fdsnws/event/1/query'
NA_BOX = {'minlatitude': 14, 'maxlatitude': 62, 'minlongitude': -125, 'maxlongitude': -60}


def gdacs(days=21):
    t = now()
    frm, to = (t - dt.timedelta(days=days)).date().isoformat(), t.date().isoformat()
    feats = []
    for ev in ('DR', 'FL', 'TC'):
        d = fetch_json(GDACS, params={'eventlist': ev, 'alertlevel': 'Green;Orange;Red', 'fromdate': frm, 'todate': to}, timeout=60, retries=2, backoff=8)
        feats += d.get('features', [])
    out = []
    for f in feats:
        p, g = f.get('properties', {}), f.get('geometry') or {}
        if g.get('type') != 'Point':
            continue
        out.append({'id': '%s%s' % (p.get('eventtype'), p.get('eventid')), 'type': p.get('eventtype'), 'alert': p.get('alertlevel'),
                    'current': p.get('iscurrent') == 'true', 'name': p.get('name', ''), 'country': p.get('country', ''),
                    'from': p.get('fromdate'), 'to': p.get('todate'), 'lat': g['coordinates'][1], 'lon': g['coordinates'][0],
                    'severity': (p.get('severitydata') or {}).get('severitytext', ''),
                    'url': (p.get('url') or {}).get('report') or 'https://www.gdacs.org/report.aspx?eventtype=%s&eventid=%s' % (p.get('eventtype'), p.get('eventid'))})
    out.sort(key=lambda e: ({'Red': 0, 'Orange': 1, 'Green': 2}.get(e['alert'], 3), e['to'] or ''), reverse=False)
    save(LAYERS + '/gdacs.json', {'asof': iso(now()), 'source': 'GDACS (UN/EC Global Disaster Alert and Coordination System) event list API', 'url': 'https://www.gdacs.org/',
                                  'window_days': days, 'events': out}, compact=True)
    return out


def _q(params):
    p = {'format': 'geojson', 'orderby': 'time'}
    p.update(params)
    return fetch_json(USGS, params=p, timeout=90, retries=2, backoff=6)


def quakes():
    t = now()
    # Global M4.5+ past 30 days (context for the COP layer)
    g = _q({'starttime': (t - dt.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S'), 'minmagnitude': 4.5, 'limit': 20000})
    recent = [[round(f['geometry']['coordinates'][0], 3), round(f['geometry']['coordinates'][1], 3), f['properties']['mag'],
               int(f['properties']['time'] / 1000), round(f['geometry']['coordinates'][2] or 0, 1), f['properties']['place'], f['id']] for f in g['features']]
    # North America 5 years M2.5+ (aggregated 0.25 degree grid + M3.0+ points)
    start = (t - dt.timedelta(days=5 * 365)).strftime('%Y-%m-%d')
    events, a = [], dt.datetime.strptime(start, '%Y-%m-%d')
    while a < t.replace(tzinfo=None):
        b = min(a + dt.timedelta(days=365), t.replace(tzinfo=None))
        d = _q(dict(NA_BOX, starttime=a.strftime('%Y-%m-%dT%H:%M:%S'), endtime=b.strftime('%Y-%m-%dT%H:%M:%S'), minmagnitude=2.5, limit=20000))
        events += d['features']
        a = b
    seen, ev = set(), []
    for f in events:
        if f['id'] in seen or f['properties']['mag'] is None:
            continue
        seen.add(f['id'])
        ev.append(f)
    cells = {}
    for f in ev:
        lo, la, dep = f['geometry']['coordinates'][:3]
        k = (round(la * 4) / 4, round(lo * 4) / 4)
        c = cells.setdefault(k, [0, 0.0, 0])
        c[0] += 1
        c[1] = max(c[1], f['properties']['mag'])
        c[2] = max(c[2], int(f['properties']['time'] / 1000))
    pts = [[round(f['geometry']['coordinates'][0], 3), round(f['geometry']['coordinates'][1], 3), f['properties']['mag'], int(f['properties']['time'] / 1000), round(f['geometry']['coordinates'][2] or 0, 1), f['properties']['place'], f['id']]
           for f in ev if f['properties']['mag'] >= 3.0]
    asof = iso(t)
    save(LAYERS + '/quakes.json', {
        'asof': asof, 'source': 'USGS Earthquake Catalog (ComCat) FDSN event service', 'url': 'https://earthquake.usgs.gov/fdsnws/event/1/',
        'recent_cols': ['lon', 'lat', 'mag', 'epoch', 'depth_km', 'place', 'id'], 'recent_m45_30d': recent,
        'na_window': {'from': start, 'to': t.strftime('%Y-%m-%d'), 'bbox': NA_BOX, 'min_mag': 2.5, 'events': len(ev)},
        'na_grid_cols': ['lat', 'lon', 'n_m25', 'max_mag', 'last_epoch'], 'na_grid': [[k[0], k[1], v[0], v[1], v[2]] for k, v in sorted(cells.items())],
        'na_m3_points': pts,
        'note': 'The USGS catalog does not label events as natural or induced. Clusters near disposal wells (Permian Basin, Oklahoma, Kansas) are consistent with induced seismicity reported by TexNet and state agencies, but this layer alone does not attribute cause.'}, compact=True)
    return {'recent': len(recent), 'na_events': len(ev), 'na_cells': len(cells)}


def _simplify(ring, step):
    out, last = [], None
    for x, y in ring:
        k = (round(x / step) * step, round(y / step) * step)
        if k != last:
            out.append([round(k[0], 3), round(k[1], 3)])
            last = k
    if len(out) >= 4 and out[0] != out[-1]:
        out.append(out[0])
    return out


def usdm(step=0.05):
    raw = fetch('https://droughtmonitor.unl.edu/data/json/usdm_current.json', headers={'User-Agent': BROWSER_UA}, timeout=120, retries=2)
    d = json.loads(raw.decode('utf-8'))
    date = None
    try:
        z = zipfile.ZipFile(io.BytesIO(fetch('https://droughtmonitor.unl.edu/data/shapefiles_m/USDM_current_M.zip', headers={'User-Agent': BROWSER_UA}, timeout=120)))
        m = re.search(r'USDM_(\d{8})', ' '.join(z.namelist()))
        if m:
            date = '%s-%s-%s' % (m.group(1)[:4], m.group(1)[4:6], m.group(1)[6:])
    except Exception as e:  # date only; polygons are still valid
        log('usdm: could not read map date from shapefile name: %s' % e)
    feats = []
    for f in d['features']:
        polys = []
        for poly in f['geometry']['coordinates']:
            rings = [_simplify(r, step) for r in poly]
            rings = [r for r in rings if len(r) >= 4]
            if rings:
                polys.append(rings)
        feats.append({'type': 'Feature', 'properties': {'dm': f['properties']['DM'], 'label': 'D%d' % f['properties']['DM']}, 'geometry': {'type': 'MultiPolygon', 'coordinates': polys}})
    save(LAYERS + '/usdm.geojson', {'type': 'FeatureCollection', 'asof': date, 'fetched': iso(now()), 'source': 'US Drought Monitor (NDMC, USDA, NOAA), current weekly map', 'url': 'https://droughtmonitor.unl.edu/',
                                    'note': 'Polygons generalised to about 5 km for web display.', 'features': feats}, compact=True)
    return {'map_date': date, 'classes': len(feats)}
