"""Data Center Water Siting: MODELED, SWUI-inspired screening score for Texas (0.25 degree cells) and a logistics-proximity table.

NOT the published SWUI. Katakam et al. (Water Research 308, 126748) define Saline Water Utilization Intensity (SWUI) in a site-level desalination
model; only the abstract was available to this build, so no formula from the paper is reproduced. This module scores where a saline source
(brackish groundwater or produced water) is plausibly near a freshwater-stressed area with data center demand, using open data only:
  brackish groundwater (USGS NBGA wells), produced-water proximity (RRC injection/disposal wells as a proxy; volumes are not public per well),
  freshwater stress (WRI Aqueduct 4.0 state baseline water stress plus current US Drought Monitor class), and data center demand (FracTracker tracker).
Weights are defaults; the browser lets users change them and recomputes the composite from the stored sub-scores."""
import math
import os

from .common import DATA, LAYERS, SRC, iso, load, log, median, now, save
from .geo import hav_km

CELL = 0.25
LAT0, LAT1, LON0, LON1 = 25.5, 36.75, -106.75, -93.25
LONGVIEW = (32.5007, -94.7405)
W_DEFAULT = {'brackish': 0.30, 'produced': 0.30, 'stress': 0.25, 'demand': 0.15}


def pip(x, y, rings):
    inside = False
    for ring in rings:
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
                inside = not inside
            j = i
    return inside


def in_multipoly(x, y, mp):
    for poly in mp:
        xs = [p[0] for p in poly[0]]
        ys = [p[1] for p in poly[0]]
        if min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys) and pip(x, y, poly):
            return True
    return False


def hash_pts(pts, step=0.1):
    h = {}
    for lon, lat in pts:
        h.setdefault((int(lat // step), int(lon // step)), []).append((lat, lon))
    return h


def count_within(h, lat, lon, km, step=0.1):
    dlat = km / 111.0
    dlon = km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    n = 0
    for i in range(int((lat - dlat) // step), int((lat + dlat) // step) + 1):
        for j in range(int((lon - dlon) // step), int((lon + dlon) // step) + 1):
            for la, lo in h.get((i, j), ()):
                if abs(la - lat) <= dlat and abs(lo - lon) <= dlon and hav_km((lat, lon), (la, lo)) <= km:
                    n += 1
    return n


def nearest(h, lat, lon, step=0.1, maxr=8):
    best = None
    for r in range(0, maxr):
        ci, cj = int(lat // step), int(lon // step)
        for i in range(ci - r, ci + r + 1):
            for j in range(cj - r, cj + r + 1):
                if max(abs(i - ci), abs(j - cj)) != r:
                    continue
                for la, lo in h.get((i, j), ()):
                    d = hav_km((lat, lon), (la, lo))
                    if best is None or d < best:
                        best = d
        if best is not None and best <= r * step * 100:
            break
    return best


def drought_class(x, y, usdm):
    cls = -1
    for f in usdm['features']:
        k = f['properties']['dm']
        if k > cls and in_multipoly(x, y, f['geometry']['coordinates']):
            cls = k
    return cls


def run():
    nbga = load(LAYERS + '/nbga_grid.json')
    swd = load(LAYERS + '/tx_swd.json')
    pw = load(LAYERS + '/pwdb_grid.json')
    dcs = load(LAYERS + '/datacenters.json')
    qk = load(LAYERS + '/quakes.json')
    usdm = load(LAYERS + '/usdm.geojson')
    states = load(LAYERS + '/us_states.geojson')
    aq = load(os.path.join(SRC, 'aqueduct_province_bws.json'))
    npdes = load(LAYERS + '/npdes_majors.json')
    if not all([nbga, swd, pw, dcs, qk, usdm, states, aq]):
        raise RuntimeError('siting inputs missing; run the dependent feeds first (nbga, pwdb, rrc, datacenters, quakes, usdm, boundaries)')
    tx = [f for f in states['features'] if f['properties']['state'] == 'TX'][0]['geometry']['coordinates']
    aq_tx = aq['data']['USA']['Texas']['score']
    h_swd = hash_pts(swd['injection_disposal'])
    h_com = hash_pts(swd['commercial_disposal'])
    dc_live = [d for d in dcs['rows'] if d['status'] != 'Cancelled']
    h_dc = hash_pts([(d['lon'], d['lat']) for d in dc_live])
    dc_mw = {}
    for d in dc_live:
        dc_mw.setdefault((int(d['lat'] // 0.1), int(d['lon'] // 0.1)), []).append(d['mw_low'] or 0)
    nb = [dict(zip(nbga['cols'], r)) for r in nbga['rows']]
    pwr = [dict(zip(pw['cols'], r)) for r in pw['rows']]
    q3 = [(p[0], p[1]) for p in qk['na_m3_points'] if LAT0 - 1 < p[1] < LAT1 + 1 and LON0 - 1 < p[0] < LON1 + 1]
    h_q = hash_pts(q3)
    cells = []
    lat = LAT0
    while lat <= LAT1:
        lon = LON0
        while lon <= LON1:
            if in_multipoly(lon, lat, tx):
                cells.append((round(lat, 3), round(lon, 3)))
            lon += CELL
        lat += CELL
    log('siting: %d Texas cells' % len(cells))
    raw = []
    for la, lo in cells:
        near = [r for r in nb if abs(r['lat'] - la) <= 0.5 and abs(r['lon'] - lo) <= 0.5]
        N = sum(r['n_samples'] for r in near)
        brack = sum(r['n_samples'] * r['pct_brackish_1000_10000'] for r in near) / N if N else None
        med = median([r['median_tds_mgL'] for r in near]) if near else None
        pn = [r for r in pwr if abs(r['lat'] - la) <= 0.5 and abs(r['lon'] - lo) <= 0.5]
        pw_tds = median([r['median_tds_mgL'] for r in pn]) if pn else None
        n_swd = count_within(h_swd, la, lo, 50)
        n_com = count_within(h_com, la, lo, 50)
        n_dc = count_within(h_dc, la, lo, 50)
        mw = 0
        for i in range(int((la - 0.5) // 0.1), int((la + 0.5) // 0.1) + 1):
            for j in range(int((lo - 0.5) // 0.1), int((lo + 0.5) // 0.1) + 1):
                for v in dc_mw.get((i, j), ()):
                    mw += v
        n_q = count_within(h_q, la, lo, 50)
        dm = drought_class(lo, la, usdm)
        raw.append({'lat': la, 'lon': lo, 'n_nbga': N, 'brackish_pct': None if brack is None else round(brack, 1), 'nbga_median_tds': None if med is None else round(med), 'pw_tds_median': None if pw_tds is None else round(pw_tds),
                    'swd_50km': n_swd, 'com_disp_50km': n_com, 'dc_50km': n_dc, 'dc_mw_known_50km': round(mw), 'm3_quakes_5y_50km': n_q, 'drought_class': dm})
    ref_swd = sorted(c['swd_50km'] for c in raw)[int(0.95 * len(raw))] or 1
    ref_dc = sorted(c['dc_50km'] for c in raw)[int(0.95 * len(raw))] or 1
    out = []
    for c in raw:
        s_b = 0.0 if c['brackish_pct'] is None else (c['brackish_pct'] / 100.0) * min(1.0, c['n_nbga'] / 20.0)
        s_p = min(1.0, math.log10(1 + c['swd_50km']) / math.log10(1 + ref_swd))
        s_s = 0.5 * (aq_tx / 5.0) + 0.5 * ((c['drought_class'] + 1) / 5.0 if c['drought_class'] >= 0 else 0.0)
        s_d = min(1.0, math.log10(1 + c['dc_50km']) / math.log10(1 + ref_dc))
        c.update({'s_brackish': round(s_b, 3), 's_produced': round(s_p, 3), 's_stress': round(s_s, 3), 's_demand': round(s_d, 3)})
        c['score'] = round(100 * (W_DEFAULT['brackish'] * s_b + W_DEFAULT['produced'] * s_p + W_DEFAULT['stress'] * s_s + W_DEFAULT['demand'] * s_d), 1)
        out.append(c)
    out.sort(key=lambda c: -c['score'])
    for i, c in enumerate(out):
        c['rank'] = i + 1
    lv = min(out, key=lambda c: hav_km((c['lat'], c['lon']), LONGVIEW))
    keys = ['lat', 'lon', 'score', 's_brackish', 's_produced', 's_stress', 's_demand', 'n_nbga', 'brackish_pct', 'nbga_median_tds', 'pw_tds_median', 'swd_50km', 'com_disp_50km', 'dc_50km', 'dc_mw_known_50km', 'm3_quakes_5y_50km', 'drought_class', 'rank']
    save(LAYERS + '/siting_tx.json', {
        'asof': iso(now()), 'label': 'MODELED / ANALYTIC ASSESSMENT', 'cell_deg': CELL, 'weights_default': W_DEFAULT, 'aqueduct_texas_bws': aq_tx, 'usdm_date': usdm.get('asof'),
        'refs': {'swd_50km_p95': ref_swd, 'dc_50km_p95': ref_dc}, 'cols': keys, 'rows': [[c[k] for k in keys] for c in out],
        'longview': {'lat': LONGVIEW[0], 'lon': LONGVIEW[1], 'cell': {k: lv[k] for k in keys}, 'of_cells': len(out)},
        'inputs': {'nbga': nbga['source'], 'swd': swd['source'], 'pwdb': pw['source'], 'datacenters': dcs['source'], 'usgs_quakes': qk['source'], 'usdm': usdm['source'], 'aqueduct': aq['citation']},
        'formula': ['s_brackish = (share of NBGA samples within 0.5 degrees with 1,000-10,000 mg/L TDS) x min(1, samples/20)', 's_produced = log10(1 + injection/disposal wells within 50 km) / log10(1 + 95th-percentile cell value)',
                    's_stress = 0.5 x (Aqueduct 4.0 Texas baseline water stress / 5) + 0.5 x (US Drought Monitor class at cell centre, D0=1 ... D4=5, / 5; 0 if none)', 's_demand = log10(1 + tracked data centers within 50 km, excluding cancelled) / log10(1 + 95th-percentile cell value)',
                    'score = 100 x (0.30 s_brackish + 0.30 s_produced + 0.25 s_stress + 0.15 s_demand)'],
        'caveats': ['Injection/disposal well counts are a proxy for produced-water presence; RRC does not publish per-well volumes in the layer used.', 'NBGA samples are historical (1901-2013).', 'Aqueduct stress is one value for all of Texas, so spatial variation in s_stress comes only from drought class.',
                    'Not a permitting, engineering or cost assessment. Treatment feasibility depends on salinity, brine management and energy (see the published paper).']}, compact=True)
    # logistics proximity for Texas data centers
    pot = [(r[0], r[1]) for r in npdes['rows'] if r[4] == 'TX' and r[6]]
    h_pot = hash_pts(pot)
    rows = []
    for d in dc_live:
        if d['state'] not in ('TX', 'Texas'):
            continue
        la, lo = d['lat'], d['lon']
        cell = min(out, key=lambda c: hav_km((c['lat'], c['lon']), (la, lo)))
        rows.append({'name': d['name'], 'county': d['county'], 'city': d['city'], 'status': d['status'], 'operator': d['operator'], 'lat': la, 'lon': lo, 'loc_conf': d['loc_conf'], 'mw_low': d['mw_low'], 'mw_high': d['mw_high'],
                     'cooling': (d['cooling_type'] or d['cooling_source']), 'swd_25km': count_within(h_swd, la, lo, 25), 'swd_50km': count_within(h_swd, la, lo, 50),
                     'nearest_commercial_disposal_km': None if (x := nearest(h_com, la, lo)) is None else round(x, 1), 'nearest_potw_major_km': None if (x := nearest(h_pot, la, lo)) is None else round(x, 1),
                     'potw_25km': count_within(h_pot, la, lo, 25), 'cell_score': cell['score'], 'cell_rank': cell['rank'], 'cell_brackish_pct': cell['brackish_pct']})
    rows.sort(key=lambda r: -(r['cell_score']))
    save(LAYERS + '/logistics_tx.json', {'asof': iso(now()), 'label': 'ANALYTIC ASSESSMENT', 'source': 'Computed from RRC injection/disposal wells, ECHO NPDES major POTWs, FracTracker data center register and the siting grid',
                                         'distance_method': 'Great-circle (haversine) distance from the listed coordinate; not a hauling or pipeline route.', 'count': len(rows), 'rows': rows}, compact=True)
    return {'cells': len(out), 'top': out[0], 'longview_rank': lv['rank'], 'longview_cell': lv, 'tx_dcs': len(rows)}
