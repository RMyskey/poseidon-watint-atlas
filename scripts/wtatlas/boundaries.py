"""US county and state boundaries (Census 2023 cartographic boundary files, 1:20,000,000) simplified for web display."""
import io
import os
import zipfile

from .common import LAYERS, RAW, download, iso, log, now, save

FILES = {'county': 'cb_county_20m.zip', 'state': 'cb_state_20m.zip'}
URL = 'https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_%s_20m.zip'
STUSPS_SKIP = {'PR', 'VI', 'GU', 'MP', 'AS'}


def _simp(ring, step=0.01):
    out, last = [], None
    for x, y in ring:
        k = (round(x / step) * step, round(y / step) * step)
        if k != last:
            out.append([round(k[0], 3), round(k[1], 3)])
            last = k
    if len(out) >= 4 and out[0] != out[-1]:
        out.append(out[0])
    return out


def _read(kind):
    import shapefile
    p = os.path.join(RAW, FILES[kind])
    if not os.path.exists(p):
        download(URL % kind, p, timeout=300)
    z = zipfile.ZipFile(p)
    b = [n for n in z.namelist() if n.endswith('.shp')][0][:-4]
    return shapefile.Reader(shp=io.BytesIO(z.read(b + '.shp')), shx=io.BytesIO(z.read(b + '.shx')), dbf=io.BytesIO(z.read(b + '.dbf')), encoding='utf-8', encodingErrors='replace')


def run():
    out = {}
    for kind in ('county', 'state'):
        feats = []
        for sr in _read(kind).iterShapeRecords():
            d = sr.record.as_dict()
            if d.get('STUSPS') in STUSPS_SKIP:
                continue
            sh = sr.shape.__geo_interface__
            polys = [sh['coordinates']] if sh['type'] == 'Polygon' else sh['coordinates']
            mp = []
            for poly in polys:
                rings = [_simp(r) for r in poly]
                rings = [r for r in rings if len(r) >= 4]
                if rings:
                    mp.append(rings)
            props = {'name': d.get('NAME'), 'state': d.get('STUSPS')}
            if kind == 'county':
                props.update({'fips': d.get('GEOID'), 'statefp': d.get('STATEFP')})
            else:
                props.update({'fips': d.get('STATEFP')})
            feats.append({'type': 'Feature', 'properties': props, 'geometry': {'type': 'MultiPolygon', 'coordinates': mp}})
        save(LAYERS + '/us_' + ('counties' if kind == 'county' else 'states') + '.geojson', {'type': 'FeatureCollection', 'asof': '2023', 'source': 'US Census Bureau cartographic boundary files 2023 (1:20m), generalised to about 1 km', 'url': 'https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html', 'features': feats}, compact=True)
        out[kind] = len(feats)
    return out
