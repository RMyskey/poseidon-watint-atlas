"""Texas Railroad Commission (RRC) public GIS: well-location density grid, injection/disposal wells, commercial disposal.

Source: https://gis.rrc.texas.gov/server/rest/services/rrc_public/RRC_Public_Viewer_Srvs/MapServer (layers 1, 3, 4).
The bulk shapefile mirror (mft.rrc.texas.gov) drops TLS handshakes from some networks, so this uses the ArcGIS REST service.
Well SYMNUM classes (RRC GIS symbol codes, returned as GIS_SYMBOL_DESCRIPTION) are grouped into: producing, shut-in, plugged, injection/disposal, other."""
import concurrent.futures as cf
import json
import urllib.parse

from .common import LAYERS, fetch, iso, log, now, save

BASE = 'https://gis.rrc.texas.gov/server/rest/services/rrc_public/RRC_Public_Viewer_Srvs/MapServer'
CELL = 0.1
PROD = {4, 5, 6}
SHUT = {19, 20}
PLUG = {7, 8, 10, 116, 118, 136, 152, 153, 117}
INJ = {11, 21, 22, 23, 104, 105, 106, 124, 126, 144}
GROUPS = ['producing', 'shut_in', 'plugged', 'injection_disposal', 'other']


def group(sym):
    if sym in PROD: return 0
    if sym in SHUT: return 1
    if sym in PLUG: return 2
    if sym in INJ: return 3
    return 4


def q(layer, params, retries=3):
    p = {'f': 'json'}
    p.update(params)
    raw = fetch(BASE + '/%d/query' % layer, params=p, timeout=60, retries=retries, backoff=3)
    d = json.loads(raw.decode('utf-8'))
    if 'error' in d:
        raise RuntimeError(str(d['error'])[:200])
    return d


def page(offset):
    d = q(1, {'where': '1=1', 'outFields': 'SYMNUM,GIS_LAT83,GIS_LONG83', 'returnGeometry': 'false', 'orderByFields': 'OBJECTID',
              'resultOffset': offset, 'resultRecordCount': 1000})
    return [(a['attributes'].get('SYMNUM'), a['attributes'].get('GIS_LAT83'), a['attributes'].get('GIS_LONG83')) for a in d.get('features', [])]


def points(layer):
    out, off = [], 0
    total = q(layer, {'where': '1=1', 'returnCountOnly': 'true'})['count']
    while off < total:
        d = q(layer, {'where': '1=1', 'outFields': 'API', 'returnGeometry': 'true', 'outSR': 4326, 'orderByFields': 'OBJECTID', 'resultOffset': off, 'resultRecordCount': 1000})
        feats = d.get('features', [])
        if not feats:
            break
        for f in feats:
            g = f.get('geometry') or {}
            if g.get('x') is not None:
                out.append([round(g['x'], 4), round(g['y'], 4)])
        off += len(feats)
    return out, total


def run(workers=8):
    total = q(1, {'where': '1=1', 'returnCountOnly': 'true'})['count']
    log('rrc: %d well records, paging 1000 at a time with %d threads' % (total, workers))
    cells, cnt, bad, byclass = {}, 0, 0, {}
    offs = list(range(0, total, 1000))
    with cf.ThreadPoolExecutor(workers) as ex:
        for res in ex.map(page, offs):
            for sym, la, lo in res:
                cnt += 1
                if la is None or lo is None or not (25 < la < 37 and -107 < lo < -93):
                    bad += 1
                    continue
                g = group(sym or 0)
                k = (round(la / CELL), round(lo / CELL))
                c = cells.get(k)
                if c is None:
                    c = cells[k] = [0, 0, 0, 0, 0]
                c[g] += 1
                byclass[g] = byclass.get(g, 0) + 1
    rows = [[round(k[0] * CELL, 2), round(k[1] * CELL, 2)] + v for k, v in sorted(cells.items())]
    asof = iso(now())
    save(LAYERS + '/tx_wells_grid.json', {
        'asof': asof, 'source': 'Railroad Commission of Texas public GIS viewer service, layer 1 Well Locations (GIS_LAT83/GIS_LONG83, NAD83)',
        'url': BASE + '/1', 'cell_deg': CELL, 'cols': ['lat', 'lon'] + GROUPS, 'rows': rows,
        'totals': {GROUPS[g]: byclass.get(g, 0) for g in range(5)}, 'records': cnt, 'skipped_bad_coords': bad,
        'note': 'Counts per 0.1 degree cell (about 11 km). Includes every well record in the RRC layer, including plugged and dry holes.'}, compact=True)
    swd, nswd = points(4)
    com, ncom = points(3)
    save(LAYERS + '/tx_swd.json', {
        'asof': asof, 'source': 'Railroad Commission of Texas, layers 4 Injection/Disposal and 3 Commercial Disposal', 'url': BASE,
        'injection_disposal': swd, 'commercial_disposal': com, 'n_injection_disposal': nswd, 'n_commercial': ncom,
        'note': 'Layer 4 includes enhanced-oil-recovery injection as well as saltwater disposal wells; the service does not separate them. Volumes are not in this layer.'}, compact=True)
    return {'wells': cnt, 'cells': len(rows), 'injection_disposal': nswd, 'commercial_disposal': ncom, 'by_class': {GROUPS[g]: byclass.get(g, 0) for g in range(5)}}
