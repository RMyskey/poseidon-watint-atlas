"""Groundwater and produced-water chemistry aggregates.

- USGS National Produced Waters Geochemical Database v3.0 (PWDB): basin statistics, 0.25 degree grid, compact point layer.
- USGS National Brackish Groundwater Assessment (NBGA) dissolved-solids dataset: 0.25 degree grid of well-sample salinity."""
import csv
import io
import os
import sys
import zipfile

from .common import LAYERS, RAW, STATE, iso, load, log, median, now, num, pctl, save, download

csv.field_size_limit(1 << 24)
PWDB_ZIP = os.path.join(RAW, 'pwdb', 'pwdb3_shape.zip')
PWDB_ZIP_URL = 'https://www.sciencebase.gov/catalog/file/get/64fa1e71d34ed30c2054ea11?f=__disk__67%2F59%2F50%2F675950d05608fa8c616d11a86281280c490eafc1'
PWDB_URL = 'https://www.sciencebase.gov/catalog/item/64fa1e71d34ed30c2054ea11'  # landing page for USGS Produced Waters DB v3.0 (DOI 10.5066/P9DSRCZJ)
NBGA_ZIP = os.path.join(RAW, 'nbga_dissolved_solids.zip')
NBGA_URL = 'https://www.sciencebase.gov/catalog/file/get/589365b5e4b0fa1e59b7331e?f=__disk__eb%2F05%2F78%2Feb0578382602d66d907149ecd312d7123dd0e084'


def pwdb():
    import shapefile
    if not os.path.exists(PWDB_ZIP):
        log('pwdb: downloading ~24 MB shapefile zip from ScienceBase')
        download(PWDB_ZIP_URL, PWDB_ZIP, timeout=600)
    z = zipfile.ZipFile(PWDB_ZIP)
    b = [n for n in z.namelist() if n.lower().endswith('.shp')][0][:-4]
    r = shapefile.Reader(shp=io.BytesIO(z.read(b + '.shp')), shx=io.BytesIO(z.read(b + '.shx')), dbf=z.open(b + '.dbf'), encoding='latin-1')
    fields = ['BASIN', 'WELLTYPE', 'PLAYTYPE', 'STATE', 'COUNTY', 'TDS', 'Cl', 'Li', 'Br', 'Ba', 'LATITUDE', 'LONGITUDE', 'COORDAPX', 'DATESAMPLE']
    basins, cells, pts, bidx, total, tds_n = {}, {}, [], {}, 0, 0
    for rec in r.iterRecords(fields=fields):
        total += 1
        rd = rec.as_dict()
        d = {k: (rd.get(k) if isinstance(rd.get(k), str) else '' if rd.get(k) is None else rd.get(k)) for k in fields}
        lat, lon = num(d['LATITUDE']), num(d['LONGITUDE'])
        if lat is None or lon is None or lat == -9999 or lon == -9999 or not (-90 <= lat <= 90):
            continue
        g = lambda k: (lambda v: None if v is None or v <= -9990 else v)(num(d[k]))
        tds, cl, li, br = g('TDS'), g('Cl'), g('Li'), g('Br')
        basin = str(d['BASIN'] or '').strip() or 'Unknown'
        if basin == '-9999':
            basin = 'Unknown'
        B = basins.setdefault(basin, {'n': 0, 'tds': [], 'cl': [], 'li': [], 'br': [], 'lat': [], 'lon': [], 'states': {}, 'welltypes': {}})
        B['n'] += 1
        B['lat'].append(lat)
        B['lon'].append(lon)
        st = str(d['STATE'] or '').strip()
        B['states'][st] = B['states'].get(st, 0) + 1
        wt = str(d['WELLTYPE'] or '').strip()
        B['welltypes'][wt] = B['welltypes'].get(wt, 0) + 1
        for k, v in (('tds', tds), ('cl', cl), ('li', li), ('br', br)):
            if v is not None and v >= 0:
                B[k].append(v)
        ca = str(d['COORDAPX'] or '').strip()
        approx = bool(ca and ca != '-9999')
        if tds is not None and tds > 0:
            tds_n += 1
            k = (round(lat * 4) / 4, round(lon * 4) / 4)
            c = cells.setdefault(k, [0, []])
            c[0] += 1
            c[1].append(tds)
            if basin not in bidx:
                bidx[basin] = len(bidx)
            pts.append([round(lon, 3), round(lat, 3), int(round(tds)), bidx[basin], 1 if approx else 0])
    out = []
    for name, B in sorted(basins.items(), key=lambda kv: -kv[1]['n']):
        out.append({'basin': name, 'n_samples': B['n'], 'n_tds': len(B['tds']), 'tds_median_mgL': median(B['tds']) and round(median(B['tds'])),
                    'tds_p10_mgL': B['tds'] and round(pctl(B['tds'], 0.1)), 'tds_p90_mgL': B['tds'] and round(pctl(B['tds'], 0.9)),
                    'cl_median_mgL': B['cl'] and round(median(B['cl'])), 'li_median_mgL': B['li'] and round(median(B['li']), 1), 'br_median_mgL': B['br'] and round(median(B['br'])),
                    'lat': round(sum(B['lat']) / len(B['lat']), 2), 'lon': round(sum(B['lon']) / len(B['lon']), 2),
                    'top_states': [s for s, _ in sorted(B['states'].items(), key=lambda kv: -kv[1])[:3] if s],
                    'top_welltype': max(B['welltypes'].items(), key=lambda kv: kv[1])[0] if B['welltypes'] else ''})
    ver = ''
    vp = os.path.join(RAW, 'pwdb', 'pwdb3_version.txt')
    if os.path.exists(vp):
        ver = 'v3.0'
    asof = iso(now())
    meta = {'asof': '2023-12-27', 'fetched': asof, 'dataset_version': 'v3.0 (December 2023); samples 1879-2022', 'source': 'USGS National Produced Waters Geochemical Database v3.0 (Blondes et al.; Scanlon et al. compilation)',
            'doi': '10.5066/P9DSRCZJ', 'url': 'https://www.sciencebase.gov/catalog/item/64fa1e71d34ed30c2054ea11', 'license': 'US Government work, public domain', 'records': total, 'records_with_tds': tds_n}
    save(LAYERS + '/pwdb_basins.json', dict(meta, basins=out), compact=True)
    save(LAYERS + '/pwdb_grid.json', dict(meta, cell_deg=0.25, cols=['lat', 'lon', 'n_tds', 'median_tds_mgL', 'max_tds_mgL'],
         rows=[[k[0], k[1], v[0], round(median(v[1])), round(max(v[1]))] for k, v in sorted(cells.items())]), compact=True)
    save(LAYERS + '/pwdb_points.json', dict(meta, cols=['lon', 'lat', 'tds_mgL', 'basin_idx', 'coord_approx'], basins=[b for b, _ in sorted(bidx.items(), key=lambda kv: kv[1])], rows=pts,
         note='coord_approx=1 means the record carries only an approximate (for example county-centroid) location.'), compact=True)
    return {'records': total, 'with_tds': tds_n, 'basins': len(out), 'cells': len(cells)}


def nbga():
    if not os.path.exists(NBGA_ZIP):
        log('nbga: downloading ~48 MB zip from ScienceBase')
        download(NBGA_URL, NBGA_ZIP, timeout=900)
    z = zipfile.ZipFile(NBGA_ZIP)
    name = [n for n in z.namelist() if n.endswith('.csv')][0]
    cells, n_rows, n_tds = {}, 0, 0
    with z.open(name) as raw:
        rd = csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8', errors='replace', newline=''))
        for row in rd:
            n_rows += 1
            lat, lon, tds = num(row.get('dec_lat_va')), num(row.get('dec_long_va')), num(row.get('TDS_mgL'))
            if lat is None or lon is None or tds is None or tds < 0:
                continue
            n_tds += 1
            k = (round(lat * 4) / 4, round(lon * 4) / 4)
            c = cells.get(k)
            if c is None:
                c = cells[k] = {'t': [], 'dep': [], 'st': row.get('state_alpha') or ''}
            c['t'].append(tds)
            dep = num(row.get('preferred_max_depth')) or num(row.get('well_depth_ft'))
            if dep and dep > 0:
                c['dep'].append(dep)
    rows = []
    for k, c in sorted(cells.items()):
        t = c['t']
        n = len(t)
        rows.append([k[0], k[1], n, round(median(t)), round(100 * sum(1 for x in t if 1000 <= x < 10000) / n), round(100 * sum(1 for x in t if x < 1000) / n),
                     round(100 * sum(1 for x in t if x >= 10000) / n), round(median(c['dep'])) if c['dep'] else None, c['st']])
    save(LAYERS + '/nbga_grid.json', {
        'asof': '2017-04-05', 'fetched': iso(now()), 'source': 'USGS Geochemical Database for the Brackish Groundwater Assessment of the United States, Dissolved-Solids Dataset',
        'doi': '10.5066/F72F7KK1', 'url': 'https://www.sciencebase.gov/catalog/item/583dfd9ee4b088b77f520d07', 'samples': n_tds, 'rows_read': n_rows, 'sample_period': '1901-10-11 to 2013-09-05',
        'cell_deg': 0.25, 'cols': ['lat', 'lon', 'n_samples', 'median_tds_mgL', 'pct_brackish_1000_10000', 'pct_fresh_lt_1000', 'pct_saline_gt_10000', 'median_depth_ft', 'state'], 'rows': rows,
        'note': 'Brackish groundwater as defined by USGS: 1,000 to 10,000 mg/L dissolved solids. Dataset publication date 2017-04-05; samples 1901-2013. It is a historical compilation, not a current monitoring feed.'}, compact=True)
    return {'samples': n_tds, 'cells': len(rows)}
