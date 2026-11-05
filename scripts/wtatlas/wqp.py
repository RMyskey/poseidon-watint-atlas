"""Water Quality Portal (WQP, USGS/EPA/USDA) groundwater-well chemistry, aggregated by county and HUC8.

Pulls zipped narrowResult CSV per state and parameter group (siteType=Well, water medium, since 2010), joins to Station metadata
(lat, lon, HUC8, county), and keeps only aggregates: count, sites, median, 90th percentile, maximum and share above each
jurisdiction's limit. Raw rows are discarded after aggregation, which is how a very large pull stays small and fast in the browser.
Per-state results are cached in data/state/wqp_cache/ so an interrupted run resumes."""
import concurrent.futures as cf
import csv
import io
import os
import zipfile

from .common import LAYERS, STATE, fetch, iso, load, log, median, now, num, pctl, save

WQP = 'https://www.waterqualitydata.us/data/'
SINCE = '01-01-2010'
FIPS = {'AL': '01', 'AK': '02', 'AZ': '04', 'AR': '05', 'CA': '06', 'CO': '08', 'CT': '09', 'DE': '10', 'DC': '11', 'FL': '12', 'GA': '13', 'HI': '15', 'ID': '16', 'IL': '17', 'IN': '18',
        'IA': '19', 'KS': '20', 'KY': '21', 'LA': '22', 'ME': '23', 'MD': '24', 'MA': '25', 'MI': '26', 'MN': '27', 'MS': '28', 'MO': '29', 'MT': '30', 'NE': '31', 'NV': '32', 'NH': '33',
        'NJ': '34', 'NM': '35', 'NY': '36', 'NC': '37', 'ND': '38', 'OH': '39', 'OK': '40', 'OR': '41', 'PA': '42', 'RI': '44', 'SC': '45', 'SD': '46', 'TN': '47', 'TX': '48', 'UT': '49',
        'VT': '50', 'VA': '51', 'WA': '53', 'WV': '54', 'WI': '55', 'WY': '56'}
# key: (WQP characteristicName values, canonical unit, display name)
PARAMS = {
    'tds': (['Total dissolved solids'], 'mg/L', 'Total dissolved solids'),
    'chloride': (['Chloride'], 'mg/L', 'Chloride'),
    'nitrate': (['Nitrate', 'Nitrate as N'], 'mg/L as N', 'Nitrate (as N)'),
    'arsenic': (['Arsenic'], 'ug/L', 'Arsenic'),
    'pfoa': (['Perfluorooctanoic acid'], 'ng/L', 'PFOA'),
    'pfos': (['Perfluorooctanesulfonate (PFOS)', 'Perfluorooctane sulfonic acid'], 'ng/L', 'PFOS'),
}
US_LIMIT = {'tds': 500, 'chloride': 250, 'nitrate': 10, 'arsenic': 10, 'pfoa': 4, 'pfos': 4}   # EPA SMCL / MCL (see data/source/reference.json limits)
CACHE = os.path.join(STATE, 'wqp_cache')


def to_canonical(key, val, unit):
    u = (unit or '').strip().lower().replace(' ', '')
    if key in ('tds', 'chloride'):
        if u in ('mg/l', 'mg/l', 'ppm'):
            return val
        if u in ('ug/l', 'ug/l'):
            return val / 1000.0
        if u == 'g/l':
            return val * 1000.0
        return None
    if key == 'nitrate':
        if u in ('mg/l', 'mg/l', 'mg/lasn', 'mg/l asn', 'ppm', 'mg/l-n', 'mg/lasn'):
            return val
        if 'no3' in u:
            return val / 4.427
        if u in ('ug/l',):
            return val / 1000.0
        if u.startswith('mg/l'):
            return val
        return None
    if key == 'arsenic':
        if u == 'ug/l':
            return val
        if u == 'mg/l':
            return val * 1000.0
        return None
    if key in ('pfoa', 'pfos'):
        if u in ('ng/l', 'ppt'):
            return val
        if u == 'ug/l':
            return val * 1000.0
        return None


def _get_zip_csv(endpoint, params, timeout=300):
    raw = fetch(WQP + endpoint, params=params, timeout=timeout, retries=2, backoff=10)
    if raw[:2] == b'PK':
        z = zipfile.ZipFile(io.BytesIO(raw))
        n = [x for x in z.namelist() if x.endswith('.csv')][0]
        return io.TextIOWrapper(z.open(n), encoding='utf-8', errors='replace', newline='')
    return io.StringIO(raw.decode('utf-8', 'replace'))


def pull(st, key):
    """Return aggregated per-site records for one state and parameter: {site: [values...]} plus station metadata."""
    cache = os.path.join(CACHE, '%s_%s.json' % (key, st))
    c = load(cache)
    if c is not None:
        return c
    names, _, _ = PARAMS[key]
    base = [('statecode', 'US:' + FIPS[st]), ('siteType', 'Well'), ('sampleMedia', 'Water'), ('startDateLo', SINCE)] + [('characteristicName', n) for n in names]
    stations = {}
    for row in csv.DictReader(_get_zip_csv('Station/search', base + [('mimeType', 'csv'), ('zip', 'yes')])):
        la, lo = num(row.get('LatitudeMeasure')), num(row.get('LongitudeMeasure'))
        if la is None or lo is None:
            continue
        stations[row['MonitoringLocationIdentifier']] = [round(la, 4), round(lo, 4), (row.get('HUCEightDigitCode') or '').strip(), (row.get('CountyCode') or '').strip().zfill(3), (row.get('StateCode') or '').strip().zfill(2)]
    sites = {}
    n_rows = n_nd = n_bad = 0
    for row in csv.DictReader(_get_zip_csv('Result/search', base + [('mimeType', 'csv'), ('zip', 'yes'), ('dataProfile', 'narrowResult')])):
        sid = row.get('MonitoringLocationIdentifier')
        if sid not in stations:
            continue
        n_rows += 1
        v = num(row.get('ResultMeasureValue'))
        det = (row.get('ResultDetectionConditionText') or '').lower()
        if 'not detected' in det or 'below' in det or (row.get('MeasureQualifierCode') or '').strip().startswith('U') and v is None:
            n_nd += 1
            continue
        if v is None:
            n_bad += 1
            continue
        cv = to_canonical(key, v, row.get('ResultMeasure/MeasureUnitCode'))
        if cv is None or cv < 0:
            n_bad += 1
            continue
        if '<' in (row.get('MeasureQualifierCode') or '') or 'u' == (row.get('MeasureQualifierCode') or '').strip().lower():
            n_nd += 1
            continue
        sites.setdefault(sid, []).append([cv, (row.get('ActivityStartDate') or '')[:4]])
    out = {'stations': {k: stations[k] for k in sites}, 'sites': sites, 'rows': n_rows, 'nd': n_nd, 'bad': n_bad}
    save(cache, out, compact=True)
    return out


def run(states=None, keys=None, workers=3):
    states = states or list(FIPS)
    keys = keys or list(PARAMS)
    jobs = [(st, k) for k in keys for st in states]
    res, errs = {}, []

    def one(j):
        try:
            return j, pull(*j), None
        except Exception as e:  # noqa: BLE001
            return j, None, '%s/%s: %s' % (j[1], j[0], str(e)[:100])

    with cf.ThreadPoolExecutor(workers) as ex:
        for j, r, e in ex.map(one, jobs):
            if e:
                errs.append(e)
                log('wqp:', e)
            else:
                res[j] = r
                if r['sites']:
                    log('wqp: %s %s sites=%d rows=%d' % (j[1], j[0], len(r['sites']), r['rows']))
    county, huc, tops, summary = {}, {}, {}, {}
    for key in keys:
        lim = US_LIMIT[key]
        cagg, hagg, site_list, tot_rows, tot_sites, over_med, over_any = {}, {}, [], 0, 0, 0, 0
        for st in states:
            r = res.get((st, key))
            if not r:
                continue
            tot_rows += sum(len(v) for v in r['sites'].values())
            for sid, vals in r['sites'].items():
                la, lo, h8, cty, stfips = r['stations'][sid]
                tot_sites += 1
                vs = [x[0] for x in vals]
                over_med += median(vs) > lim
                over_any += max(vs) > lim
                yr = max((x[1] for x in vals if x[1]), default='')
                fips = stfips + cty if cty and cty != '000' else None
                for agg, k in ((cagg, fips), (hagg, h8)):
                    if k:
                        a = agg.setdefault(k, {'v': [], 'sites': 0, 'lat': 0.0, 'lon': 0.0, 'yr': ''})
                        a['v'] += vs
                        a['sites'] += 1
                        a['lat'] += la
                        a['lon'] += lo
                        a['yr'] = max(a['yr'], yr)
                site_list.append((max(vs), sid, la, lo, st, len(vs), yr))
        fmt = lambda a: [len(a['v']), a['sites'], round(median(a['v']), 3), round(pctl(a['v'], 0.9), 3), round(max(a['v']), 3), round(100 * sum(1 for x in a['v'] if x > lim) / len(a['v']), 1), a['yr']]
        county[key] = {k: fmt(a) for k, a in cagg.items()}
        huc[key] = [[k, round(a['lat'] / a['sites'], 3), round(a['lon'] / a['sites'], 3)] + fmt(a) for k, a in hagg.items()]
        site_list.sort(reverse=True)
        tops[key] = [[round(v, 3), sid, la, lo, st, n, yr] for v, sid, la, lo, st, n, yr in site_list[:150]]
        summary[key] = {'results': tot_rows, 'sites': tot_sites, 'counties': len(cagg), 'huc8': len(hagg), 'sites_over_limit': over_med, 'sites_any_over_limit': over_any, 'limit': lim}
    meta = {'asof': iso(now()), 'source': 'Water Quality Portal (USGS, EPA, USDA-ARS), siteType=Well, sampleMedia=Water, results since 2010-01-01', 'url': 'https://www.waterqualitydata.us/',
            'params': {k: {'name': PARAMS[k][2], 'unit': PARAMS[k][1], 'us_limit': US_LIMIT[k]} for k in keys}, 'summary': summary, 'errors': errs[:20],
            'cols': ['n_results', 'n_sites', 'median', 'p90', 'max', 'pct_above_us_limit', 'latest_year']}
    save(LAYERS + '/wqp_county.json', dict(meta, data=county), compact=True)
    save(LAYERS + '/wqp_huc8.json', dict(meta, cols=['huc8', 'lat', 'lon'] + meta['cols'], data=huc), compact=True)
    save(LAYERS + '/wqp_top_sites.json', dict(meta, cols=['max_value', 'site_id', 'lat', 'lon', 'state', 'n_results', 'latest_year'], data=tops), compact=True)
    return {'summary': summary, 'errors': len(errs)}
