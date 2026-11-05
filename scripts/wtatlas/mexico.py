"""Mexico (CONAGUA open data) processing: aquifer availability, groundwater and surface water quality sites, treatment plant catalogs,
drought monitor and the piezometric network.

CONAGUA's open-data host (https://sinav30.conagua.gob.mx:8080/docs/DatosAbiertos/) sits behind an Imperva WAF and often resets automated
TLS connections. This module therefore reads files from data/state/raw/mx/ (downloaded once from the CONAGUA data portal) and only tries a
live download when a file is missing; a failed download leaves the previous outputs in place."""
import csv
import io
import os
import re
import sys
import zipfile

from .common import LAYERS, RAW, download, iso, log, median, now, num, save

MX = os.path.join(RAW, 'mx')
BASE = 'https://sinav30.conagua.gob.mx:8080/docs/DatosAbiertos/'
FILES = {
    'aq': 'Acuiferos_Disponibilidad_09-11-2023.zip',
    'wq_data': 'Datos_de_calidad_del_agua_de_5000_sitios_de_monitoreo.zip',
    'wq_res': 'Resultados_de_calidad_del_agua_de_5000_sitios_de_monitoreo.zip',
    'ptar': 'Catalogo_de_Plantas_de_Tratamiento_Aguas_Residuales.csv',
    'potab': 'Catalogo_de_Plantas_Potabilizadoras_Municipales_en_Operacion.csv',
    'piezo': 'Red_piezometrica_mapas.csv',
    'drought': 'Monitor_de_Sequia_en_Mexico.zip',
    'basins': 'Disponibilidad_media_de_agua_superficial_por_cuenca.csv',
    'pressure': 'Indicador_grado_de_presion_sobre_recursos_hidricos.csv',
}


def path(k):
    return os.path.join(MX, 'mx_' + FILES[k])


def ensure():
    missing = []
    for k in FILES:
        if not os.path.exists(path(k)):
            try:
                download(BASE + FILES[k], path(k), timeout=120)
            except Exception as e:  # noqa: BLE001
                missing.append('%s (%s)' % (FILES[k], str(e)[:60]))
    if missing:
        raise RuntimeError('CONAGUA files unavailable: ' + '; '.join(missing[:3]))


def fix(s):
    return (s or '').strip()


def rdr(raw, enc='latin-1'):
    return csv.DictReader(io.StringIO(raw.decode(enc, 'replace').lstrip('\ufeff')))


def simplify(ring, step):
    out, last = [], None
    for x, y in ring:
        k = (round(x / step) * step, round(y / step) * step)
        if k != last:
            out.append([round(k[0], 3), round(k[1], 3)])
            last = k
    if len(out) >= 4 and out[0] != out[-1]:
        out.append(out[0])
    return out


def aquifers():
    import shapefile
    z = zipfile.ZipFile(path('aq'))
    b = [n for n in z.namelist() if n.endswith('.shp')][0][:-4]
    r = shapefile.Reader(shp=io.BytesIO(z.read(b + '.shp')), shx=io.BytesIO(z.read(b + '.shx')), dbf=io.BytesIO(z.read(b + '.dbf')), encoding='utf-8', encodingErrors='replace')
    feats, deficit_n, tot_pos, tot_neg = [], 0, 0.0, 0.0
    for sr in r.iterShapeRecords():
        d = sr.record.as_dict()
        sh = sr.shape.__geo_interface__
        polys = [sh['coordinates']] if sh['type'] == 'Polygon' else sh['coordinates']
        mp = []
        for poly in polys:
            rings = [simplify(rg, 0.02) for rg in poly]
            rings = [x for x in rings if len(x) >= 4]
            if rings:
                mp.append(rings)
        dmp, dmn = num(d.get('DMA_POSITI')) or 0.0, num(d.get('DMA_NEGATI')) or 0.0
        tot_pos += dmp
        tot_neg += dmn
        deficit_n += dmn < 0
        feats.append({'type': 'Feature', 'properties': {'id': d.get('CLV_ACUI'), 'name': d.get('NOM_ACUI'), 'state': d.get('NOM_EDO'), 'region': d.get('NOM_REGION'), 'area_km2': d.get('AREA_KM2'),
                                                          'recharge_hm3': d.get('RECARGA_TO'), 'concessioned_hm3': d.get('VCAS'), 'avail_hm3': round(dmp, 3), 'deficit_hm3': round(dmn, 3)},
                      'geometry': {'type': 'MultiPolygon', 'coordinates': mp}})
    save(LAYERS + '/mx_aquifers.geojson', {'type': 'FeatureCollection', 'asof': '2023-11-09', 'source': 'CONAGUA, Disponibilidad de agua subterranea por acuifero (datos abiertos)', 'url': 'https://sinav30.conagua.gob.mx:8080/',
                                           'note': 'Coordinates are NAD27 geographic as published, displayed as WGS84 (offset about 100 m, negligible at this generalisation of about 2 km). Volumes in hm3 per year (million cubic metres). avail = DMA positive, deficit = DMA negative.',
                                           'features': feats}, compact=True)
    return {'aquifers': len(feats), 'in_deficit': deficit_n, 'total_avail_hm3': round(tot_pos), 'total_deficit_hm3': round(tot_neg)}


def quality():
    sites = []
    zd = zipfile.ZipFile(path('wq_data'))
    g = [n for n in zd.namelist() if 'subterraneas' in n and n.endswith('.csv')][0]
    for r in rdr(zd.read(g)):
        la, lo = num(r.get('LATITUD')), num(r.get('LONGITUD'))
        if la is None or lo is None:
            continue
        sites.append({'t': 'gw', 'id': fix(r.get('CLAVE')), 'n': fix(r.get('SITIO')).title(), 'st': fix(r.get('ESTADO')).title(), 'mun': fix(r.get('MUNICIPIO')).title(), 'aq': fix(r.get('ACUIFERO')).title(),
                      'lat': round(la, 5), 'lon': round(lo, 5), 'yr': fix(r.get('PERIODO')), 'tds': num(r.get('SDT_mg/L')), 'no3n': num(r.get('N_NO3_mg/L')), 'as_mgL': num(r.get('AS_TOT_mg/L')),
                      'f': num(r.get('FLUORUROS_mg/L')), 'fe': num(r.get('FE_TOT_mg/L')), 'mn': num(r.get('MN_TOT_mg/L')), 'pb': num(r.get('PB_TOT_mg/L')), 'flag': fix(r.get('SEMAFORO')),
                      'subtype': fix(r.get('SUBTIPO')).title(), 'contam': fix(r.get('CONTAMINANTES'))[:60]})
    zr = zipfile.ZipFile(path('wq_res'))
    sw = 0
    for r in rdr(zr.read('Resultados_de_calidad_del_agua_de_5000_sitios_de_monitoreo.csv')):
        la, lo = num(r.get('LATITUD')), num(r.get('LONGITUD'))
        if la is None or lo is None:
            continue
        sw += 1
        sites.append({'t': 'sw', 'id': fix(r.get('CLAVE')), 'n': fix(r.get('SITIO')).title(), 'st': fix(r.get('ESTADO')).title(), 'mun': fix(r.get('MUNICIPIO')).title(), 'aq': '',
                      'lat': round(la, 5), 'lon': round(lo, 5), 'yr': fix(r.get('ANIO')), 'tds': num(r.get('SDT_mg/L')), 'bod': num(r.get('DBO_mg/L')), 'cod': num(r.get('DQO_mg/L')), 'tss': num(r.get('SST_mg/L')),
                      'flag': fix(r.get('SEMAFORO')), 'subtype': fix(r.get('SUBTIPO')).title(), 'contam': ''})
    sites = [{k: v for k, v in s.items() if v not in (None, '')} for s in sites]
    save(LAYERS + '/mx_quality_sites.json', {'asof': '2021 (groundwater campaign); surface results by site year', 'source': 'CONAGUA RNMCA water-quality monitoring sites (datos abiertos): groundwater 2021 and surface-water results',
                                             'url': 'https://sinav30.conagua.gob.mx:8080/', 'groundwater_sites': len(sites) - sw, 'surface_sites': sw,
                                             'note': 'Values as published by CONAGUA (mg/L). Non-detects (< values) are left blank. Traffic-light flag is CONAGUA\'s own classification.', 'sites': sites}, compact=True)
    return {'groundwater': len(sites) - sw, 'surface': sw}


def plants():
    def agg(rows, name_k, state_k, cap_k, flow_k, status_k=None):
        by = {}
        for r in rows:
            nm = fix(r.get(name_k))
            if not nm:
                continue
            st = fix(r.get(state_k)).title()
            cap, fl = num(r.get(cap_k)), num(r.get(flow_k))
            S = by.setdefault(st, {'n': 0, 'cap_lps': 0.0, 'flow_lps': 0.0})
            S['n'] += 1
            S['cap_lps'] += cap or 0
            S['flow_lps'] += fl or 0
        return by
    ptar_rows = [r for r in rdr(open(path('ptar'), 'rb').read()) if fix(r.get('Nombre de la PTAR'))]
    keys = list(ptar_rows[0].keys())
    ck = [k for k in keys if k.startswith('Capacidad')][0]
    fk = [k for k in keys if k.startswith('Caudal')][0]
    sk = [k for k in keys if k.startswith('Estado de op')][0]
    active = [r for r in ptar_rows if fix(r.get(sk)).lower() == 'activa']
    ptar = agg(active, 'Nombre de la PTAR', 'Estado', ck, fk)
    pot_rows = list(rdr(open(path('potab'), 'rb').read()))
    pk = list(pot_rows[0].keys())
    pot = agg(pot_rows, pk[3], pk[0], pk[4], pk[5])
    proc = {}
    for r in active:
        p = fix(r.get(keys[7]))
        proc[p] = proc.get(p, 0) + 1
    save(LAYERS + '/mx_plants.json', {'asof': '2023', 'source': 'CONAGUA catalogues: municipal wastewater treatment plants (PTAR, 2023 status) and municipal potabilization plants in operation', 'url': 'https://sinav30.conagua.gob.mx:8080/',
                                      'wastewater_by_state': ptar, 'potabilization_by_state': pot, 'ptar_processes': dict(sorted(proc.items(), key=lambda kv: -kv[1])[:12]),
                                      'totals': {'ptar_listed': len(ptar_rows), 'ptar_active': len(active), 'ptar_capacity_lps': round(sum(v['cap_lps'] for v in ptar.values())), 'ptar_treated_lps': round(sum(v['flow_lps'] for v in ptar.values())),
                                                 'potab_plants': len(pot_rows), 'potab_capacity_lps': round(sum(v['cap_lps'] for v in pot.values())), 'potab_flow_lps': round(sum(v['flow_lps'] for v in pot.values()))},
                                      'note': 'The catalogues carry locality names, not coordinates, so they are shown at state level. Flows in litres per second.'}, compact=True)
    return {'ptar_active': len(active), 'potab': len(pot_rows)}


def drought():
    z = zipfile.ZipFile(path('drought'))
    names = z.namelist()
    tipo = [n for n in names if 'Tipo_Sequia' in n][0]
    date = re.match(r'(\d{4})_(\d{2})_(\d{2})', os.path.basename(tipo))
    d = '%s-%s-%s' % date.groups() if date else None
    states = []
    for r in rdr(z.read(tipo)):
        ent = fix(r.get('ENTIDAD'))
        if not ent:
            continue
        states.append({'state': ent, 'D0': int(num(r.get('D0')) or 0), 'D1': int(num(r.get('D1')) or 0), 'D2': int(num(r.get('D2')) or 0), 'D3': int(num(r.get('D3')) or 0), 'D4': int(num(r.get('D4')) or 0),
                       'municipalities_in_drought_d1_d4': int(num(r.get('MUNICIPIOS  CON SEQUÍA (D1 - D4)')) or num(r.get('MUNICIPIOS  CON SEQU\x00DA (D1 - D4)')) or 0)})
    # recompute D1-D4 from classes (header encoding differs between releases)
    for s in states:
        s['municipalities_in_drought_d1_d4'] = s['D1'] + s['D2'] + s['D3'] + s['D4']
    save(LAYERS + '/mx_drought.json', {'asof': d, 'source': 'CONAGUA / SMN Monitor de Sequia en Mexico (municipal drought classes)', 'url': 'https://smn.conagua.gob.mx/es/climatologia/monitor-de-sequia/monitor-de-sequia-en-mexico',
                                       'states': states, 'totals': {k: sum(s[k] for s in states) for k in ('D0', 'D1', 'D2', 'D3', 'D4', 'municipalities_in_drought_d1_d4')}}, compact=True)
    return {'asof': d, 'states': len(states)}


def basins_pressure():
    rows = list(rdr(open(path('pressure'), 'rb').read(), 'utf-8'))
    pr = [{'class': fix(r.get('Clasificacion del grado de presion')), 'region': fix(r.get('Region Hidrologico-Administrativa')), 'pct': num(r.get('Valor')), 'year': fix(r.get('Año'))} for r in rows]
    b = list(rdr(open(path('basins'), 'rb').read()))
    bk = list(b[0].keys())
    deficit = sum(1 for r in b if 'ficit' in (r.get(bk[-1]) or ''))
    save(LAYERS + '/mx_pressure.json', {'asof': '2014 (indicator)', 'source': 'CONAGUA grado de presion sobre los recursos hidricos (by hydrological-administrative region) and mean surface availability by basin', 'url': 'https://sinav30.conagua.gob.mx:8080/',
                                        'pressure': pr, 'basins_total': len(b), 'basins_deficit': deficit}, compact=True)
    return {'regions': len(pr), 'basins': len(b), 'deficit': deficit}


def piezo():
    rows = [r for r in rdr(open(path('piezo'), 'rb').read())]
    pts, aq = [], {}
    for r in rows:
        la, lo = num(r.get('LATITUD')), num(r.get('LONGITUD'))
        if la is None or lo is None or not (14 < la < 33 and -119 < lo < -86):
            continue
        pts.append([round(lo, 3), round(la, 3)])
        a = fix(r.get('ACUIFERO')).title()
        aq[a] = aq.get(a, 0) + 1
    save(LAYERS + '/mx_piezo.json', {'asof': '2023 (network map file)', 'source': 'CONAGUA piezometric network (Red piezometrica)', 'url': 'https://sinav30.conagua.gob.mx:8080/', 'wells': len(pts),
                                     'cols': ['lon', 'lat'], 'rows': pts, 'aquifers': len(aq), 'note': 'Station locations only; depth time series are in the CONAGUA file and not republished here.'}, compact=True)
    return {'wells': len(pts), 'aquifers': len(aq)}


def run():
    ensure()
    out = {}
    for fn in (aquifers, quality, plants, drought, basins_pressure, piezo):
        out[fn.__name__] = fn()
    return out
