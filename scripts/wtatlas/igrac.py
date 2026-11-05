"""IGRAC GGIS public WFS: Global Groundwater Monitoring Network points (level + quality).
Aggregated to 1 degree cells and a per-country table. Raw pages are not kept."""
import json, urllib.parse, concurrent.futures as cf
from .common import *

WFS = 'https://ggis.un-igrac.org/geoserver/ows'
LAYER = 'groundwater:Global_Groundwater_Monitoring_Network_(GGMN)'
PROPS = 'location,feature_type,country,groundwater_level_data,groundwater_quality_data,status,last_recorded_measurement'
PAGE = 20000


def _url(extra):
    q = dict(service='WFS', version='2.0.0', request='GetFeature', typeNames=LAYER)
    q.update(extra)
    return WFS + '?' + urllib.parse.urlencode(q)


def run():
    hits = fetch(_url(dict(resultType='hits')), retries=3).decode('utf-8', 'replace')
    import re
    total = int(re.search(r'numberMatched="(\d+)"', hits).group(1))
    starts = list(range(0, total, PAGE))
    pages = {}

    def get(s):
        u = _url(dict(count=PAGE, startIndex=s, sortBy='id', outputFormat='application/json', propertyName=PROPS))
        return s, fetch_json(u, retries=4)

    with cf.ThreadPoolExecutor(4) as ex:
        for s, j in ex.map(get, starts):
            pages[s] = j['features']
            log('igrac page %d: %d' % (s, len(j['features'])))
    grid, ctry = {}, {}
    n = 0
    lastmax = ''
    for s in sorted(pages):
        for f in pages[s]:
            p = f['properties']
            g = f.get('geometry')
            if not g or g.get('type') != 'Point':
                continue
            lon, lat = g['coordinates'][:2]
            n += 1
            lv = (p.get('groundwater_level_data') or 0) > 0
            ql = (p.get('groundwater_quality_data') or 0) > 0
            k = '%d,%d' % (int(lat // 1), int(lon // 1))
            c = grid.setdefault(k, [0, 0, 0])
            c[0] += 1
            c[1] += lv
            c[2] += ql
            cn = p.get('country') or 'Unknown'
            C = ctry.setdefault(cn, {'sites': 0, 'level': 0, 'quality': 0, 'springs': 0})
            C['sites'] += 1
            C['level'] += lv
            C['quality'] += ql
            C['springs'] += (p.get('feature_type') == 'Spring')
            lm = (p.get('last_recorded_measurement') or '')[:10]
            if lm > lastmax and lm <= today():
                lastmax = lm
    cells = [[int(k.split(',')[0]) + .5, int(k.split(',')[1]) + .5] + v for k, v in grid.items()]
    out = {'meta': {'source': 'IGRAC GGIS public WFS (Global Groundwater Monitoring Network layer)', 'url': 'https://ggis.un-igrac.org/', 'asof': today(), 'asof_note': 'Layer is edited continuously; latest measurement date seen: ' + lastmax,
                    'records': n, 'matched': total, 'cell_deg': 1, 'cell_cols': ['lat', 'lon', 'sites', 'with_level_series', 'with_quality_series'], 'precision': 'G',
                    'note': 'GGMN is a registry of participating national monitoring points. It is not a complete global well inventory and carries no chemistry values here; quality counts are the number of quality measurements recorded at the site per IGRAC, not exceedances.'},
           'cells': cells, 'countries': dict(sorted(ctry.items(), key=lambda kv: -kv[1]['sites']))}
    save(LAYERS + '/ggmn_global.json', out, compact=True)
    log('igrac done sites=%d cells=%d countries=%d' % (n, len(cells), len(ctry)))
    return n
