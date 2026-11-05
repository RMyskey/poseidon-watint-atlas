"""North America oil & gas well registries beyond Texas (open, unclassified regulator data).

New Mexico  EMNRD Oil Conservation Division (OCD) ArcGIS REST: Wells_Public (well status/type) + Well_Injection (per-well injection totals).
Oklahoma    Corporation Commission (OCC) ArcGIS REST: RBDMS_WELLS, ALL_UIC_WELLS, COMMERCIAL_UIC_WELLS + annual Form 1012 UIC volume workbook.
Alberta     Alberta Energy Regulator (AER) ST37 List of Wells (Excel package, monthly).
British Columbia  BC Energy Regulator via BC Data Catalogue WFS (OG_SURFACE_HOLE_STATUS_SP).
Saskatchewan  Ministry of Energy and Resources "Petroleum Wells" ArcGIS REST layer.
Mexico      SENER completed-wells CSV on datos.gob.mx: attempted, blocked from this network (see mx_wells).

Every jurisdiction writes the same two layers as Texas: <j>_wells_grid.json (0.1 degree cell counts by class) and <j>_swd.json (injection/disposal points).
Class names are the atlas's own grouping of each regulator's status codes; the mapping is in the layer note. Counts are record counts, not wells drilled."""
import collections
import concurrent.futures as cf
import datetime as dt
import json
import os
import urllib.parse
import zipfile

from .common import LAYERS, RAW, download, fetch, fetch_json, iso, log, now, save

CELL = 0.1
GROUPS = ['producing', 'shut_in', 'plugged', 'injection_disposal', 'other']
P, S, G, I, O = range(5)
UA = 'Mozilla/5.0 (X11; Linux x86_64) PoseidonWATINT/1.0'


def _grid(jur, source, url, classed, note, extra=None):
    """classed: iterable of (lat, lon, class_index)."""
    cells, tot, n, bad = {}, [0] * 5, 0, 0
    for la, lo, g in classed:
        n += 1
        if la is None or lo is None or not (-90 < la < 90 and -180 < lo < 180) or (la == 0 and lo == 0):
            bad += 1
            continue
        k = (round(la / CELL), round(lo / CELL))
        c = cells.get(k)
        if c is None:
            c = cells[k] = [0] * 5
        c[g] += 1
        tot[g] += 1
    rows = [[round(k[0] * CELL, 2), round(k[1] * CELL, 2)] + v for k, v in sorted(cells.items())]
    out = {'asof': iso(now()), 'jur': jur, 'source': source, 'url': url, 'cell_deg': CELL, 'cols': ['lat', 'lon'] + GROUPS, 'rows': rows,
           'totals': {GROUPS[i]: tot[i] for i in range(5)}, 'records': n, 'skipped_bad_coords': bad, 'note': note}
    if extra:
        out.update(extra)
    save(LAYERS + '/%s_wells_grid.json' % jur.lower(), out, compact=True)
    return out


def _arc_pages(base, params, total, size, workers=6):
    def one(off):
        p = dict(params)
        p.update({'f': 'json', 'resultOffset': off, 'resultRecordCount': size})
        d = json.loads(fetch(base + '/query', params=p, timeout=90, retries=3, backoff=4, ua=UA).decode('utf-8'))
        if 'error' in d:
            raise RuntimeError(str(d['error'])[:200])
        return d.get('features', [])
    with cf.ThreadPoolExecutor(workers) as ex:
        for feats in ex.map(one, list(range(0, total, size))):
            yield from feats


def _count(base, where='1=1'):
    d = json.loads(fetch(base + '/query', params={'where': where, 'returnCountOnly': 'true', 'f': 'json'}, timeout=60, ua=UA).decode('utf-8'))
    return d['count']


# ---------------------------------------------------------------- New Mexico
NM = 'https://gis.emnrd.nm.gov/arcgis/rest/services/OCDView'


def nm_class(typ, st):
    typ, st = (typ or '').strip(), (st or '').strip()
    if st.startswith('Plugged') or st.startswith('Zone Plugged (perm') or st == 'Reclamation Fund Approved':
        return G
    if typ in ('Salt Water Disposal', 'Injection') and st in ('Active', 'New', 'Temporary Abandonment', 'Temporary Abandonment (expired)'):
        return I
    if typ in ('Oil', 'Gas', 'CO2', 'C02') and st == 'Active':
        return P
    if st.startswith('Temporary Abandonment') or st.startswith('Zone Plugged (temp'):
        return S
    return O


def nm():
    base = NM + '/Wells_Public/MapServer/0'
    total = _count(base)
    log('nm: %d OCD well records' % total)
    rows, swd = [], {}
    for f in _arc_pages(base, {'where': '1=1', 'outFields': 'id,type,status,latitude,longitude', 'returnGeometry': 'false', 'orderByFields': 'OBJECTID'}, total, 2000):
        a = f['attributes']
        g = nm_class(a.get('type'), a.get('status'))
        rows.append((a.get('latitude'), a.get('longitude'), g))
        if g == I:
            swd[a.get('id')] = [a.get('longitude'), a.get('latitude'), None, 0 if a.get('type') == 'Salt Water Disposal' else 1]
    # per-well injection totals (rolling 12 months and lifetime)
    vb = NM + '/Well_Injection/MapServer/2'
    nv = _count(vb)
    vols, win, lastinj = {}, None, 0
    for f in _arc_pages(vb, {'where': '1=1', 'outFields': 'API,SUMINJLASTYEAR,SUMINJAMT,STARTMONTHFORYRCALC,LASTINJ,NUMMONTHS', 'returnGeometry': 'false', 'orderByFields': 'OBJECTID'}, nv, 2000):
        a = f['attributes']
        vols[a['API']] = (a.get('SUMINJLASTYEAR'), a.get('SUMINJAMT'))
        win = a.get('STARTMONTHFORYRCALC') or win
        lastinj = max(lastinj, a.get('LASTINJ') or 0)
    joined, vsum, vwells = 0, 0, 0
    for api, p in swd.items():
        v = vols.get(api)
        if v and v[0] is not None:
            p[2] = int(v[0])
            joined += 1
            vsum += int(v[0])
            vwells += 1 if v[0] > 0 else 0
    note = ('Atlas grouping of OCD type and status: producing = Oil/Gas/CO2 and Active; shut-in = Temporary Abandonment or Zone Plugged (temporary); plugged = Plugged, Zone Plugged (permanent) or Reclamation Fund Approved; '
            'injection/disposal = type Injection or Salt Water Disposal that is Active, New or Temporarily Abandoned; other = Cancelled, New (permit only), Never Drilled, Dry Hole, Miscellaneous, Water. Well locations are from form C-102 and are approximate per OCD.')
    g = _grid('NM', 'New Mexico EMNRD Oil Conservation Division, Wells_Public (New Mexico Oil and Gas Wells)', NM + '/Wells_Public/MapServer/0', rows, note)
    pts = sorted(swd.values(), key=lambda p: (p[1] or 0, p[0] or 0))
    save(LAYERS + '/nm_swd.json', {
        'asof': g['asof'], 'jur': 'NM', 'source': 'New Mexico OCD Wells_Public (locations) joined by API number to Well_Injection layer 2 (rolling 12-month injection total)',
        'url': NM + '/Well_Injection/MapServer', 'cols': ['lon', 'lat', 'vol_12m', 'subtype'], 'subtypes': ['saltwater disposal', 'injection (EOR/other)'],
        'injection_disposal': pts, 'commercial_disposal': [], 'n_injection_disposal': len(pts), 'n_commercial': 0,
        'volume_window': {'start_yyyymm': win, 'last_report_yyyymm': lastinj, 'months': 12},
        'volume_wells_joined': joined, 'volume_wells_nonzero': vwells, 'volume_total_12m': vsum,
        'volume_note': 'SUMINJLASTYEAR from the OCD Well_Injection service (rolling 12-month window beginning STARTMONTHFORYRCALC). The service metadata does not state a unit; OCD injection reports (form C-115) are in barrels, so the figure is read as barrels. Treat totals as ANALYTIC ASSESSMENT until confirmed with OCD.'}, compact=True)
    return {'wells': g['records'], 'cells': len(g['rows']), 'injection_disposal': len(pts), 'volume_wells': vwells, 'by_class': g['totals']}


# ---------------------------------------------------------------- Oklahoma
OKB = 'https://gis.occ.ok.gov/server/rest/services/Hosted'
OK_INJ = {'2RIn', '2DNC', '2DCm', '2RSI', 'INJ', 'SWD', '2R', '2RIN', 'LPSW', '2D', '2DCM'}


def ok_class(wt, st):
    wt, st = (wt or '').strip(), (st or '').strip().upper()
    if st.startswith('PA'):
        return G
    if wt in OK_INJ and st in ('AC', 'ACRT', 'SIFORDER', 'TA', 'SFFO', 'OR', 'NE'):
        return I if st in ('AC', 'ACRT') else O
    if st == 'AC' and wt in ('OIL', 'GAS', 'OG', 'GSTOR'):
        return P
    if st in ('TA', 'SIFORDER', 'SI'):
        return S
    return O


def _ok_volumes(year=2025):
    """Parse the OCC annual UIC injection volume workbook (Form 1012). Returns {api: (total, fluid, measurement)}."""
    import openpyxl
    url = 'https://oklahoma.gov/content/dam/ok/en/occ/documents/og/ogdatafiles/%d-uic-injection-volumes.xlsx' % year
    dest = RAW + '/ok_uic_%d.xlsx' % year
    download(url, dest, ua=UA, min_bytes=100000)
    wb = openpyxl.load_workbook(dest, read_only=True)
    ws = wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    h = list(next(it))
    ix = {n: i for i, n in enumerate(h)}
    vc = [ix[m + ' Vol'] for m in ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')]
    out = {}
    for r in it:
        if not r or r[ix['API']] is None:
            continue
        tot = sum((r[i] or 0) for i in vc if isinstance(r[i], (int, float)))
        k = int(r[ix['API']])
        prev = out.get(k)
        out[k] = ((prev[0] if prev else 0) + tot, r[ix['FluidType']], r[ix['MeasurementType']], r[ix['WellType']])
    return out, year, url


def ok():
    base = OKB + '/RBDMS_WELLS/FeatureServer/2'
    total = _count(base)
    log('ok: %d OCC well records' % total)
    rows = []
    for f in _arc_pages(base, {'where': '1=1', 'outFields': 'welltype,wellstatus,sh_lat,sh_lon', 'returnGeometry': 'false', 'orderByFields': 'objectid'}, total, 2000):
        a = f['attributes']
        rows.append((a.get('sh_lat'), a.get('sh_lon'), ok_class(a.get('welltype'), a.get('wellstatus'))))
    note = ('Atlas grouping of OCC RBDMS well type/status codes: producing = status AC with type OIL/GAS/OG; shut-in = TA or SIFORDER; plugged = any PA* status; injection/disposal = UIC well types (2RIn, 2DNC, 2DCm, 2RSI, INJ, SWD) with status AC; '
            'other = remaining codes (NE, OR, EX, ND, STFD, dry, not typed, test, water-supply). OCC status codes are applied as published; unmapped codes fall in other.')
    g = _grid('OK', 'Oklahoma Corporation Commission, RBDMS_WELLS hosted feature service', OKB + '/RBDMS_WELLS/FeatureServer/2', rows, note)
    # UIC wells (active) with annual volumes
    ub = OKB + '/ALL_UIC_WELLS/FeatureServer/249'
    cb = OKB + '/COMMERCIAL_UIC_WELLS/FeatureServer/254'
    uic = [f['attributes'] for f in _arc_pages(ub, {'where': '1=1', 'outFields': 'api,well_type,status,lat,lon,bbls', 'returnGeometry': 'false', 'orderByFields': 'objectid'}, _count(ub), 2000)]
    com = [f['attributes'] for f in _arc_pages(cb, {'where': '1=1', 'outFields': 'api,lat,lon', 'returnGeometry': 'false', 'orderByFields': 'objectid'}, _count(cb), 2000)]
    vol_err, vols, vyear, vurl = None, {}, None, None
    for y in (dt.date.today().year, dt.date.today().year - 1, dt.date.today().year - 2):
        try:
            vols, vyear, vurl = _ok_volumes(y)
            break
        except Exception as e:  # volume workbook for the newest year may not exist yet
            vol_err = str(e)[:140]
    comset = {int(c['api']) for c in com if c.get('api')}
    pts, cpts, joined, vsum = [], [], 0, 0
    for a in uic:
        if a.get('lat') is None or a.get('lon') is None:
            continue
        v = vols.get(int(a['api'])) if a.get('api') else None
        vol = None
        if v and (v[1] or '').upper().startswith('SALT') or (v and v[1] is None):
            vol = int(v[0])
            joined += 1
            vsum += vol
        pts.append([round(a['lon'], 5), round(a['lat'], 5), vol, 0 if (a.get('well_type') or '') in ('2DNC', '2DCm') else 1])
    for c in com:
        if c.get('lat') is not None and c.get('lon') is not None:
            cpts.append([round(c['lon'], 5), round(c['lat'], 5)])
    save(LAYERS + '/ok_swd.json', {
        'asof': g['asof'], 'jur': 'OK', 'source': 'Oklahoma Corporation Commission ALL_UIC_WELLS and COMMERCIAL_UIC_WELLS (active Class II UIC wells) joined by API number to the OCC annual UIC injection volume workbook',
        'url': ub, 'cols': ['lon', 'lat', 'vol_year', 'subtype'], 'subtypes': ['disposal (2DNC/2DCm)', 'enhanced recovery / other injection'],
        'injection_disposal': pts, 'commercial_disposal': cpts, 'n_injection_disposal': len(pts), 'n_commercial': len(cpts),
        'volume_year': vyear, 'volume_source': vurl, 'volume_wells_joined': joined, 'volume_total_year': vsum, 'volume_error': vol_err,
        'volume_note': 'Sum of the twelve monthly Vol columns in the OCC workbook for saltwater wells (Form 1012). The workbook does not state a unit; OCC UIC volume reports are in barrels, so the figure is read as barrels. Gas-injection wells are excluded. Treat totals as ANALYTIC ASSESSMENT.'}, compact=True)
    return {'wells': g['records'], 'cells': len(g['rows']), 'injection_disposal': len(pts), 'commercial_disposal': len(cpts), 'volume_wells': joined, 'volume_year': vyear, 'by_class': g['totals']}


# ---------------------------------------------------------------- Alberta
AB_URL = 'https://static.aer.ca/prd/documents/sts/st37/ST_37_Excel.zip'


def _xlsx_rows(zf, member):
    import openpyxl
    path = zf.extract(member, RAW + '/ab')
    wb = openpyxl.load_workbook(path, read_only=True)
    it = wb.worksheets[0].iter_rows(values_only=True)
    h = [str(x).strip() for x in next(it)]
    for r in it:
        yield dict(zip(h, r))


def ab():
    dest = RAW + '/ab/ST_37_Excel.zip'
    sz = download(AB_URL, dest, ua=UA, min_bytes=10_000_000, timeout=900)
    log('ab: ST37 package %.0f MB' % (sz / 1e6))
    zf = zipfile.ZipFile(dest)
    names = {os.path.basename(n): n for n in zf.namelist()}
    sh = {}
    for r in _xlsx_rows(zf, names['ST37_SH.xlsx']):
        lic = str(r['Well_Licence_Number']).strip()
        sh[lic] = (r['SH_Actual_Latitude'], r['SH_Actual_Longitude'], str(r['Licence_Status'] or '').strip())
    best = {}   # licence -> class index with priority
    swd_kind = {}
    rank = {I: 5, P: 4, S: 3, G: 2, O: 1}

    def put(lic, g):
        if rank[g] > rank.get(best.get(lic), 0):
            best[lic] = g
    prod_modes = ('FLOWING', 'PUMPING', 'GAS LIFT')
    for r in _xlsx_rows(zf, names['ST37_ Production_Strings.xlsx']):
        lic = str(r['Well_Licence_Number']).strip()
        mode, typ, fl = (r['Status_Mode'] or '').strip(), (r['Status_Type'] or '').strip(), (r['Status_Fluid'] or '').strip()
        if typ in ('DISPOSAL', 'INJECTION') and not mode.startswith('ABANDON') and mode not in ('JUNKED & ABANDONED',):
            put(lic, I)
            swd_kind[lic] = max(swd_kind.get(lic, 0), 0) if typ == 'DISPOSAL' else swd_kind.get(lic, 1)
            if typ == 'DISPOSAL':
                swd_kind[lic] = 0
        elif mode in prod_modes:
            put(lic, P)
        elif mode == 'SUSPENDED':
            put(lic, S)
        elif mode.startswith('ABANDON') or mode == 'JUNKED & ABANDONED':
            put(lic, G)
        else:
            put(lic, O)
    rows, pts, nostring = [], [], 0
    for lic, (la, lo, ls) in sh.items():
        g = best.get(lic)
        if g is None:
            nostring += 1
            g = G if ls in ('Abandoned', 'RecCertified', 'RecExempt') else O
        rows.append((la, lo, g))
        if g == I and la is not None and lo is not None:
            pts.append([round(lo, 5), round(la, 5), None, swd_kind.get(lic, 1)])
    note = ('Atlas grouping of AER ST37 production-string status (one class per licence, highest rank wins): injection/disposal = a string with Status_Type DISPOSAL or INJECTION that is not abandoned; '
            'producing = Status_Mode FLOWING, PUMPING or GAS LIFT; shut-in = SUSPENDED; plugged = ABANDONED (incl. zone, re-entered, whipstocked); other = the rest (drilled and cased, testing, no production string). '
            'Licences with no production string are plugged if licence status is Abandoned, RecCertified or RecExempt, otherwise other. Surface-hole positions (SH_Actual_Latitude/Longitude).')
    g = _grid('AB', 'Alberta Energy Regulator, ST37: List of Wells in Alberta (Excel package: surface holes + production strings)', 'https://www.aer.ca/providing-information/data-and-reports/statistical-reports/st37', rows, note,
              {'licences_without_string': nostring})
    save(LAYERS + '/ab_swd.json', {
        'asof': g['asof'], 'jur': 'AB', 'source': 'Alberta Energy Regulator ST37 (production strings with Status_Type DISPOSAL or INJECTION, not abandoned)', 'url': 'https://www.aer.ca/providing-information/data-and-reports/statistical-reports/st37',
        'cols': ['lon', 'lat', 'vol', 'subtype'], 'subtypes': ['disposal', 'injection (EOR, steam, solvent, other)'],
        'injection_disposal': pts, 'commercial_disposal': [], 'n_injection_disposal': len(pts), 'n_commercial': 0,
        'volume_note': 'ST37 is a well list and carries no injection volumes; none are ingested for Alberta.'}, compact=True)
    return {'wells': g['records'], 'cells': len(g['rows']), 'injection_disposal': len(pts), 'by_class': g['totals']}


# ---------------------------------------------------------------- British Columbia
BC_WFS = 'https://openmaps.gov.bc.ca/geo/pub/ows'
BC_LAYER = 'pub:WHSE_MINERAL_TENURE.OG_SURFACE_HOLE_STATUS_SP'


def bc_class(act, op, fluid):
    act, op = (act or '').strip(), (op or '').strip()
    if act in ('ABAN', 'ABNZ'):
        return G
    if op in ('INJ', 'DISP') and act in ('ACT', 'SUSP', 'DSUS'):
        return I
    if act == 'ACT' and op == 'PROD':
        return P
    if act in ('SUSP', 'DSUS'):
        return S
    return O


def bc():
    rows, pts, start, n = [], [], 0, 0
    while True:
        d = fetch_json(BC_WFS, params={'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature', 'typeNames': BC_LAYER, 'outputFormat': 'application/json', 'count': 10000, 'startIndex': start,
                                       'sortBy': 'OBJECTID', 'srsName': 'EPSG:4326', 'propertyName': 'GEOMETRY,WELL_ACTIVITY,OPERATION_TYPE,BORE_FLUID_TYPE'}, timeout=120, retries=3, backoff=5, ua=UA)
        fs = d.get('features', [])
        for f in fs:
            p, g = f['properties'], f.get('geometry') or {}
            c = g.get('coordinates') or [None, None]
            k = bc_class(p.get('WELL_ACTIVITY'), p.get('OPERATION_TYPE'), p.get('BORE_FLUID_TYPE'))
            rows.append((c[1], c[0], k))
            if k == I and c[0] is not None:
                pts.append([round(c[0], 5), round(c[1], 5), None, 0 if p.get('OPERATION_TYPE') == 'DISP' else 1])
        n += len(fs)
        start += 10000
        if len(fs) < 10000:
            break
    note = ('Atlas grouping of BC Energy Regulator surface-hole status: producing = WELL_ACTIVITY ACT with OPERATION_TYPE PROD; shut-in = SUSP or DSUS; plugged = ABAN or ABNZ; injection/disposal = OPERATION_TYPE INJ or DISP while ACT/SUSP/DSUS; '
            'other = authorised-not-drilled (WAG), cancelled, cased, completed, drilling, observation, source-water and undefined. Surface-hole points.')
    g = _grid('BC', 'BC Energy Regulator via BC Data Catalogue: Oil and Gas Well Surface Hole Status (WFS)', 'https://catalogue.data.gov.bc.ca/dataset/well-surface-hole-status', rows, note)
    save(LAYERS + '/bc_swd.json', {
        'asof': g['asof'], 'jur': 'BC', 'source': 'BC Energy Regulator surface-hole status (OPERATION_TYPE INJ or DISP, active or suspended)', 'url': 'https://catalogue.data.gov.bc.ca/dataset/well-surface-hole-status',
        'cols': ['lon', 'lat', 'vol', 'subtype'], 'subtypes': ['disposal', 'injection'], 'injection_disposal': pts, 'commercial_disposal': [], 'n_injection_disposal': len(pts), 'n_commercial': 0,
        'volume_note': 'This layer carries no injection volumes; none are ingested for British Columbia.'}, compact=True)
    return {'wells': g['records'], 'cells': len(g['rows']), 'injection_disposal': len(pts), 'by_class': g['totals']}


# ---------------------------------------------------------------- Saskatchewan
SK = 'https://gis.saskatchewan.ca/arcgis/rest/services/Petroleum/MapServer/0'


def sk_class(cat, mode):
    cat, mode = (cat or '').strip(), (mode or '').strip()
    if mode.startswith('ABD') or mode == 'PARTLY ABND' or mode == 'ABANDONED':
        return G
    if cat in ('INJECTION', 'DISPOSAL') and mode in ('ACTIVE', 'NON-ACTIVE', 'SUSPENDED'):
        return I
    if mode == 'ACTIVE' and cat in ('OIL', 'GAS'):
        return P
    if mode in ('SUSPENDED', 'NON-ACTIVE'):
        return S
    return O


def sk():
    total = _count(SK)
    rows, pts = [], []
    for f in _arc_pages(SK, {'where': '1=1', 'outFields': 'FLUID_CAT,MODE_', 'returnGeometry': 'true', 'outSR': 4326, 'orderByFields': 'OBJECTID'}, total, 1000, workers=4):
        a, g = f['attributes'], f.get('geometry') or {}
        k = sk_class(a.get('FLUID_CAT'), a.get('MODE_'))
        rows.append((g.get('y'), g.get('x'), k))
        if k == I and g.get('x') is not None:
            pts.append([round(g['x'], 5), round(g['y'], 5), None, 0 if a.get('FLUID_CAT') == 'DISPOSAL' else 1])
    note = ('Atlas grouping of Saskatchewan Petroleum Wells FLUID_CAT and MODE_: producing = OIL or GAS category and MODE_ ACTIVE; shut-in = SUSPENDED or NON-ACTIVE; plugged = any ABD* or PARTLY ABND mode; injection/disposal = FLUID_CAT INJECTION or DISPOSAL while active, non-active or suspended; '
            'other = licensed, cased, completed, cancelled, stratigraphic/potash tests, water-source.')
    g = _grid('SK', 'Saskatchewan Ministry of Energy and Resources, Petroleum Wells (ArcGIS REST layer, Production Data Warehouse)', SK, rows, note)
    save(LAYERS + '/sk_swd.json', {
        'asof': g['asof'], 'jur': 'SK', 'source': 'Saskatchewan Petroleum Wells layer (FLUID_CAT INJECTION or DISPOSAL, not abandoned)', 'url': SK,
        'cols': ['lon', 'lat', 'vol', 'subtype'], 'subtypes': ['disposal', 'injection'], 'injection_disposal': pts, 'commercial_disposal': [], 'n_injection_disposal': len(pts), 'n_commercial': 0,
        'volume_note': 'This layer carries no injection volumes; none are ingested for Saskatchewan.'}, compact=True)
    return {'wells': g['records'], 'cells': len(g['rows']), 'injection_disposal': len(pts), 'by_class': g['totals']}


# ---------------------------------------------------------------- Mexico (documented gap)
MX_URL = 'https://repodatos.atdt.gob.mx/api_update/sener/coordenadas_pozos_terminados_2026/dgace_pozos_terminados_ago_2026.csv'


def mx_probe():
    """SENER publishes monthly CSVs of completed development wells (2026 only) on datos.gob.mx. The host answers 403 Access Denied
    to automated clients from this network, so this probe only records availability; it never fabricates a layer."""
    try:
        raw = fetch(MX_URL, timeout=40, retries=1, ua=UA)
        if raw[:1] == b'<':
            raise RuntimeError('HTML (access denied) instead of CSV')
    except Exception as e:
        raise RuntimeError('SENER completed-wells CSV not retrievable: %s' % str(e)[:120])
    # a retrievable file would be ingested here; the schema is unknown from this network, so stop rather than guess
    raise RuntimeError('CSV is reachable but no verified schema is implemented; add a parser once the columns are confirmed')


# ---------------------------------------------------------------- summary across jurisdictions
JURS = [('TX', 'Texas', 'Railroad Commission of Texas', 'rrc'), ('NM', 'New Mexico', 'NM Oil Conservation Division', 'nm_ocd'), ('OK', 'Oklahoma', 'Oklahoma Corporation Commission', 'ok_occ'),
        ('AB', 'Alberta', 'Alberta Energy Regulator', 'ab_aer'), ('BC', 'British Columbia', 'BC Energy Regulator', 'bc_bcer'), ('SK', 'Saskatchewan', 'Saskatchewan Ministry of Energy and Resources', 'sk_er')]


def summary():
    """Small cross-jurisdiction table for the Oil & gas page; built only from layers already on disk."""
    from .common import load
    out, top = [], []
    for j, name, pub, sid in JURS:
        g = load(LAYERS + '/%s_wells_grid.json' % j.lower())
        s = load(LAYERS + '/%s_swd.json' % j.lower())
        if not g:
            continue
        row = {'jur': j, 'name': name, 'publisher': pub, 'src': sid, 'asof': g.get('asof'), 'records': g.get('records'), 'by_class': g.get('totals'),
               'injection_disposal_points': (s or {}).get('n_injection_disposal'), 'commercial_disposal': (s or {}).get('n_commercial')}
        if s and s.get('volume_total_12m') is not None:
            pts = s['injection_disposal']
            row['volume'] = {'kind': 'rolling 12 months', 'total': s['volume_total_12m'], 'wells': s.get('volume_wells_nonzero'), 'unit_assumed': 'barrels',
                             'swd_only_total': sum(p[2] for p in pts if p[2] and p[3] == 0), 'window': s.get('volume_window')}
            top += [{'jur': j, 'lon': p[0], 'lat': p[1], 'vol': p[2], 'subtype': s['subtypes'][p[3]]} for p in pts if p[2]]
        elif s and s.get('volume_total_year') is not None:
            pts = s['injection_disposal']
            row['volume'] = {'kind': 'calendar year %s' % s.get('volume_year'), 'total': s['volume_total_year'], 'wells': sum(1 for p in pts if p[2]), 'unit_assumed': 'barrels',
                             'swd_only_total': sum(p[2] for p in pts if p[2] and p[3] == 0)}
            top += [{'jur': j, 'lon': p[0], 'lat': p[1], 'vol': p[2], 'subtype': s['subtypes'][p[3]]} for p in pts if p[2]]
        out.append(row)
    top.sort(key=lambda x: -x['vol'])
    save(LAYERS + '/og_na_summary.json', {'asof': iso(now()), 'jurisdictions': out, 'top_volume_wells': top[:25],
                                          'note': 'Texas has no per-well volumes in the RRC layers. Volumes for NM and OK are as published by the regulators; the unit is not stated in the services and is read as barrels (ANALYTIC ASSESSMENT).'}, compact=True)
    return {'jurisdictions': len(out)}
