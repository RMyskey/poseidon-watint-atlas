"""EPA ECHO: Safe Drinking Water Act (SDWIS) community water systems and Clean Water Act (NPDES) major dischargers.

ECHO REST services (https://echo.epa.gov/tools/web-services):
  sdw_rest_services.get_systems / get_download  -> public water systems (state queries)
  cwa_rest_services.get_facilities / get_download -> NPDES permitted facilities (state queries)
Aggregates are written to data/layers/*.json; nothing here touches curated data."""
import csv
import io
import time

from .common import LAYERS, fetch, fetch_json, iso, log, median, now, num, save

ECHO = 'https://echodata.epa.gov/echo/'
STATES = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT',
          'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
SDW_COLS = '2,4,6,10,12,14,17,21,22,48,57,58,50'   # PWSId, StateCode, CountiesServed, TypeCode, PrimarySourceCode, Population, OwnerType, SeriousViolator, HealthFlag, FIPS, CurrVio, VioFlag, GwSwCode
CWA_COLS = '1,2,5,14,26,27,28,29,30,62,99,101,163,164,206'


def _rows(service, params, cols, retries=3):
    last = None
    for a in range(retries):
        try:
            d = fetch_json(ECHO + service + '.get_' + ('systems' if service.startswith('sdw') else 'facilities'), params=dict(params, output='JSON', qcolumns=cols), timeout=90, retries=2, backoff=5)
            qid = d['Results']['QueryID']
            raw = fetch(ECHO + service + '.get_download', params={'output': 'CSV', 'qid': qid, 'qcolumns': cols}, timeout=180, retries=2, backoff=5)
            return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig', 'replace'))))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(4 * (a + 1))
    raise last


def sdwa():
    systems = []
    errs = []
    for st in STATES:
        try:
            for r in _rows('sdw_rest_services', {'p_st': st, 'p_act': 'Y'}, SDW_COLS):
                systems.append(r)
        except Exception as e:  # noqa: BLE001
            errs.append('%s: %s' % (st, str(e)[:80]))
        time.sleep(0.5)
    if not systems:
        raise RuntimeError('no SDWA rows returned; ' + '; '.join(errs[:3]))
    cws = [r for r in systems if r.get('PWSTypeCode') == 'CWS']
    state, county, flow = {}, {}, {}
    bins = [(500, '500 or fewer'), (3300, '501 to 3,300'), (10000, '3,301 to 10,000'), (100000, '10,001 to 100,000'), (10 ** 12, 'More than 100,000')]
    for r in systems:
        t = r.get('PWSTypeCode') or ''
        s = r.get('StateCode') or ''
        S = state.setdefault(s, {'systems': 0, 'cws': 0, 'cws_pop': 0, 'cws_health_viol': 0, 'cws_serious': 0, 'cws_curr_viol': 0, 'cws_gw': 0, 'cws_sw': 0, 'cws_gw_pop': 0, 'cws_sw_pop': 0, 'ntnc': 0, 'tnc': 0})
        S['systems'] += 1
        if t != 'CWS':
            S['ntnc' if t == 'NTNCWS' else 'tnc'] += 1
            continue
        pop = int(num(r.get('PopulationServedCount')) or 0)
        S['cws'] += 1
        S['cws_pop'] += pop
        hv = (r.get('HealthFlag') or '').strip().upper() in ('Y', 'YES')
        serious = (r.get('SeriousViolator') or '').strip().upper() in ('Y', 'YES')
        curr = (r.get('CurrVioFlag') or '').strip() == '1'
        S['cws_health_viol'] += hv
        S['cws_serious'] += serious
        S['cws_curr_viol'] += curr
        gw = (r.get('GwSwCode') or r.get('PrimarySourceCode') or '').startswith('G')
        size = [b[1] for b in bins if pop <= b[0]][0]
        fk = ('Groundwater' if gw else 'Surface water', size, 'Health-based violation' if hv else 'No health-based violation flag')
        F = flow.setdefault(fk, [0, 0])
        F[0] += 1
        F[1] += pop
        S['cws_gw' if gw else 'cws_sw'] += 1
        S['cws_gw_pop' if gw else 'cws_sw_pop'] += pop
        for fips in (r.get('FIPSCodes') or '').replace(';', ',').split(','):
            fips = fips.strip()
            if len(fips) == 5 and fips.isdigit():
                C = county.setdefault(fips, [0, 0, 0, 0])
                C[0] += 1
                C[1] += pop
                C[2] += hv
                C[3] += serious
    asof = iso(now())
    meta = {'asof': asof, 'source': 'EPA ECHO SDWA REST services (SDWIS Fed data), active public water systems', 'url': 'https://echo.epa.gov/tools/web-services/facility-search-drinking-water'}
    save(LAYERS + '/sdwa_state.json', dict(meta, states=state, errors=errs, flow=[[k[0], k[1], k[2], v[0], v[1]] for k, v in sorted(flow.items())],
         flow_cols=['source', 'size_by_population_served', 'violation', 'systems', 'population_served'],
         flow_note='Community water systems only. Size bins follow the EPA system-size categories. Violation flag is the ECHO HealthFlag field (Yes = the system has violations of health-based standards: MCL, MRDL or treatment technique). It is a system-level flag, not a measure of exposure.'), compact=True)
    save(LAYERS + '/sdwa_county.json', dict(meta, cols=['systems_cws', 'population_served_sum', 'health_based_violation_systems', 'serious_violators'], counties=county,
         note='Community water systems are attributed to every county in their FIPSCodes list, so population served may be counted in more than one county.'), compact=True)
    return {'systems': len(systems), 'cws': len(cws), 'counties': len(county), 'states': len(state), 'errors': len(errs)}


def npdes():
    rows, errs = [], []
    for st in STATES:
        try:
            rows += _rows('cwa_rest_services', {'p_st': st, 'p_act': 'Y', 'p_maj': 'Y'}, CWA_COLS)
        except Exception as e:  # noqa: BLE001
            errs.append('%s: %s' % (st, str(e)[:80]))
        time.sleep(0.5)
    if not rows:
        raise RuntimeError('no NPDES rows returned; ' + '; '.join(errs[:3]))
    out = []
    for r in rows:
        la, lo = num(r.get('FacLat')), num(r.get('FacLong'))
        if la is None or lo is None or not (15 < la < 72 and -170 < lo < -60):
            continue
        fl = num(r.get('CWPTotalDesignFlowNmbr'))
        out.append([round(lo, 4), round(la, 4), (r.get('CWPName') or '').strip().title()[:60], r.get('SourceID'), r.get('CWPState'), (r.get('FacStdCountyName') or '').title(),
                    1 if (r.get('CWPFacilityTypeIndicator') or '').upper() == 'POTW' else 0, fl, num(r.get('CWPActualAverageFlowNmbr')), r.get('CWPSNCStatus') or r.get('CWPVioStatus') or ''])
    save(LAYERS + '/npdes_majors.json', {
        'asof': iso(now()), 'source': 'EPA ECHO CWA REST services (ICIS-NPDES), active major permittees', 'url': 'https://echo.epa.gov/tools/web-services/facility-search-water',
        'cols': ['lon', 'lat', 'name', 'permit_id', 'state', 'county', 'is_potw', 'design_flow_mgd', 'actual_avg_flow_mgd', 'compliance_status'], 'rows': out, 'errors': errs,
        'note': 'Major dischargers only (the large municipal and industrial permits). Minor permits and general permits are not included. Flow units are millions of gallons per day as reported by ECHO.'}, compact=True)
    return {'facilities': len(out), 'potw': sum(1 for x in out if x[6]), 'errors': len(errs)}
