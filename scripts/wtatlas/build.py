"""Validate curated sources, assemble derived outputs (meta, sources, cop, flow, findings) and the browser bundle assets/js/data.js."""
import os, json, math
from .common import *

OUT = DATA
PIPE = os.path.join(DATA, 'state')

# id: (title, file, source id, precision, label, records(fn), note)
def _n(k):
    return lambda j: len(j.get(k) or [])

LAYER_DEFS = [
 ('tx_wells_grid', 'Texas wells by 0.1 degree cell (producing, shut-in, plugged, injection/disposal, other)', 'tx_wells_grid.json', 'rrc', 'G', 'OBSERVED', lambda j: j.get('records'), 'Counts per cell from RRC well locations (the densest well layer). Other jurisdictions are separate layers below.'),
 ('tx_swd', 'Texas injection/disposal wells and commercial disposal sites', 'tx_swd.json', 'rrc', 'F', 'OBSERVED', lambda j: (j.get('n_injection_disposal') or 0) + (j.get('n_commercial') or 0), 'Layer 4 includes EOR injection as well as saltwater disposal; the service does not separate them.'),
 ('nm_wells_grid', 'New Mexico wells by 0.1 degree cell (New Mexico OCD)', 'nm_wells_grid.json', 'nm_ocd', 'G', 'OBSERVED', lambda j: j.get('records'), 'Counts per cell; the class mapping from regulator status codes is in the layer file note. Locations are regulator-reported.'),
 ('nm_swd', 'New Mexico injection/disposal wells', 'nm_swd.json', 'nm_ocd', 'F', 'OBSERVED', lambda j: (j.get('n_injection_disposal') or 0) + (j.get('n_commercial') or 0), 'Injection and disposal wells that are not abandoned. Rolling 12-month volumes (read as barrels; unit not stated by the service) where joined.'),
 ('ok_wells_grid', 'Oklahoma wells by 0.1 degree cell (Oklahoma OCC)', 'ok_wells_grid.json', 'ok_occ', 'G', 'OBSERVED', lambda j: j.get('records'), 'Counts per cell; the class mapping from regulator status codes is in the layer file note. Locations are regulator-reported.'),
 ('ok_swd', 'Oklahoma injection/disposal wells and commercial disposal', 'ok_swd.json', 'ok_occ', 'F', 'OBSERVED', lambda j: (j.get('n_injection_disposal') or 0) + (j.get('n_commercial') or 0), 'Injection and disposal wells that are not abandoned. 2025 monthly volumes (read as barrels; unit not stated in the workbook) where joined.'),
 ('ab_wells_grid', 'Alberta wells by 0.1 degree cell (Alberta AER ST37)', 'ab_wells_grid.json', 'ab_aer', 'G', 'OBSERVED', lambda j: j.get('records'), 'Counts per cell; the class mapping from regulator status codes is in the layer file note. Locations are regulator-reported.'),
 ('ab_swd', 'Alberta injection/disposal wells', 'ab_swd.json', 'ab_aer', 'F', 'OBSERVED', lambda j: (j.get('n_injection_disposal') or 0) + (j.get('n_commercial') or 0), 'Injection and disposal wells that are not abandoned. No volumes in this layer.'),
 ('bc_wells_grid', 'British Columbia wells by 0.1 degree cell (BC Energy Regulator)', 'bc_wells_grid.json', 'bc_bcer', 'G', 'OBSERVED', lambda j: j.get('records'), 'Counts per cell; the class mapping from regulator status codes is in the layer file note. Locations are regulator-reported.'),
 ('bc_swd', 'British Columbia injection/disposal wells', 'bc_swd.json', 'bc_bcer', 'F', 'OBSERVED', lambda j: (j.get('n_injection_disposal') or 0) + (j.get('n_commercial') or 0), 'Injection and disposal wells that are not abandoned. No volumes in this layer.'),
 ('sk_wells_grid', 'Saskatchewan wells by 0.1 degree cell (Saskatchewan Energy and Resources)', 'sk_wells_grid.json', 'sk_er', 'G', 'OBSERVED', lambda j: j.get('records'), 'Counts per cell; the class mapping from regulator status codes is in the layer file note. Locations are regulator-reported.'),
 ('sk_swd', 'Saskatchewan injection/disposal wells', 'sk_swd.json', 'sk_er', 'F', 'OBSERVED', lambda j: (j.get('n_injection_disposal') or 0) + (j.get('n_commercial') or 0), 'Injection and disposal wells that are not abandoned. No volumes in this layer.'),
 ('og_na_summary', 'North America oil and gas: records, classes and reported injection volumes by jurisdiction', 'og_na_summary.json', 'rrc', 'C', 'ANALYTIC ASSESSMENT', lambda j: sum((x.get('records') or 0) for x in j.get('jurisdictions', [])), 'Cross-jurisdiction table built from the layers above; volume totals only for NM and OK.'),
 ('quakes', 'USGS earthquakes: global M4.5+ 30 d; North America M2.5+ 5 y by 0.5 degree cell', 'quakes.json', 'usgs_quakes', 'G', 'OBSERVED', lambda j: (j.get('na_window') or {}).get('events'), 'Events are not labelled natural or induced by USGS.'),
 ('pwdb_basins', 'Produced-water chemistry by basin (USGS PWDB v3.0)', 'pwdb_basins.json', 'pwdb', 'C', 'OBSERVED', lambda j: j.get('records'), 'Medians of reported TDS and chloride per basin.'),
 ('pwdb_grid', 'Produced-water TDS by 0.25 degree cell', 'pwdb_grid.json', 'pwdb', 'G', 'OBSERVED', lambda j: j.get('records_with_tds'), ''),
 ('pwdb_points', 'Produced-water sample points (TDS)', 'pwdb_points.json', 'pwdb', 'A', 'OBSERVED', lambda j: len(j.get('rows') or []), 'Many records carry county-centroid or approximate coordinates (flag in the file).'),
 ('nbga_grid', 'Brackish groundwater salinity by cell (USGS NBGA)', 'nbga_grid.json', 'nbga', 'G', 'OBSERVED', lambda j: j.get('samples'), 'Historical samples 1901-2013, 0.25 degree cells.'),
 ('sdwa_state', 'Public water systems by state (SDWIS via ECHO), plus size/source/violation flow table', 'sdwa_state.json', 'echo_sdwa', 'C', 'OBSERVED', lambda j: sum(v['systems'] for v in j['states'].values()), 'Active systems: CWS, NTNCWS, TNCWS.'),
 ('sdwa_county', 'Community water systems by county', 'sdwa_county.json', 'echo_sdwa', 'C', 'OBSERVED', lambda j: len(j.get('counties') or {}), 'A system is attributed to every county in its FIPS list.'),
 ('npdes_majors', 'Active major NPDES dischargers (POTW and industrial)', 'npdes_majors.json', 'echo_npdes', 'F', 'OBSERVED', lambda j: len(j.get('rows') or []), 'Major permittees only.'),
 ('wqp_county', 'WQP groundwater chemistry by county, 2010 onward', 'wqp_county.json', 'wqp', 'C', 'OBSERVED', None, 'Medians, maxima and exceedance counts against EPA limits; aggregation hides individual wells.'),
 ('wqp_huc8', 'WQP groundwater chemistry by HUC8 watershed', 'wqp_huc8.json', 'wqp', 'C', 'OBSERVED', None, ''),
 ('wqp_top_sites', 'WQP highest-result groundwater sites per parameter', 'wqp_top_sites.json', 'wqp', 'M', 'OBSERVED', None, 'Top 200 sites per parameter, individual results.'),
 ('datacenters', 'US data center register (FracTracker)', 'datacenters.json', 'datacenters', 'A', 'OBSERVED', lambda j: j.get('records'), 'Third-party compiled; no water-use figures.'),
 ('siting_tx', 'Texas data-center water siting score by 0.25 degree cell', 'siting_tx.json', 'paper', 'G', 'MODELED', lambda j: len(j.get('rows') or []), 'MODELED screening inspired by the SWUI concept; not the published method.'),
 ('logistics_tx', 'Texas data centers: distance to disposal wells, commercial disposal and major POTWs', 'logistics_tx.json', 'datacenters', 'A', 'ANALYTIC ASSESSMENT', lambda j: j.get('count'), 'Great-circle distances; not haul routes.'),
 ('ca_dwa', 'First Nations long-term drinking water advisories (Canada)', 'ca_dwa.json', 'isc_dwa', 'F', 'OBSERVED', lambda j: j.get('active_ltdwa'), 'Active advisories shown; on-reserve public systems only.'),
 ('ca_wser', 'Canadian wastewater systems under WSER', 'ca_wser.json', 'wser', 'F', 'OBSERVED', lambda j: len(j.get('rows') or []), ''),
 ('mx_aquifers', 'Mexico aquifer availability (DMA, hm3/yr)', 'mx_aquifers.geojson', 'conagua', 'C', 'OBSERVED', lambda j: len(j.get('features') or []), 'Generalised polygons (about 2 km).'),
 ('mx_quality_sites', 'Mexico RNMCA water-quality sites', 'mx_quality_sites.json', 'conagua', 'M', 'OBSERVED', lambda j: len(j.get('sites') or []), 'NOM-127 comparison in the explorer.'),
 ('mx_plants', 'Mexico treatment and potabilization plants by state', 'mx_plants.json', 'conagua', 'C', 'OBSERVED', lambda j: (j.get('totals') or {}).get('ptar_listed'), 'State level only; the catalogues have no coordinates.'),
 ('mx_drought', 'Mexico drought monitor (municipalities by class, by state)', 'mx_drought.json', 'conagua', 'C', 'OBSERVED', lambda j: (j.get('totals') or {}).get('municipalities_in_drought_d1_d4'), ''),
 ('mx_pressure', 'Mexico water pressure index and basin deficits', 'mx_pressure.json', 'conagua', 'C', 'OBSERVED', lambda j: j.get('basins_total'), 'Indicator year 2014.'),
 ('mx_piezo', 'Mexico piezometric network stations', 'mx_piezo.json', 'conagua', 'M', 'OBSERVED', lambda j: j.get('wells'), 'Locations only.'),
 ('ggmn_global', 'IGRAC Global Groundwater Monitoring Network registry (1 degree cells, country table)', 'ggmn_global.json', 'igrac', 'G', 'OBSERVED', lambda j: (j.get('meta') or {}).get('records'), 'A registry of participating monitoring points; not a complete global inventory.'),
 ('gdacs', 'GDACS drought, flood and cyclone events (21 days)', 'gdacs.json', 'gdacs', 'E', 'OBSERVED', lambda j: len(j.get('events') or []), ''),
 ('usdm', 'US Drought Monitor current map', 'usdm.geojson', 'usdm', 'C', 'OBSERVED', lambda j: len(j.get('features') or []), 'Generalised to about 5 km.'),
 ('cop', 'Global WATINT COP (Oct 23 snapshot + live GDACS)', 'cop.json', 'cop', 'E', 'CURATED', lambda j: len(j.get('points') or []), 'Snapshot is never overwritten by feeds.'),
 ('us_counties', 'US county boundaries (Census 2023, 1:20m)', 'us_counties.geojson', 'census', 'C', 'OBSERVED', lambda j: len(j.get('features') or []), ''),
 ('us_states', 'US state boundaries (Census 2023, 1:20m)', 'us_states.geojson', 'census', 'C', 'OBSERVED', lambda j: len(j.get('features') or []), ''),
]


def _asof(j):
    if not isinstance(j, dict):
        return None
    if 'asof' in j:
        return j['asof']
    return (j.get('meta') or {}).get('asof')


def wqp_summary():
    j = load(LAYERS + '/wqp_county.json') or {}
    return j.get('summary') or j.get('meta', {}).get('summary') or {}


def validate(ref, src):
    err = []
    for k in ('precision', 'limits', 'labels', 'footer', 'regions'):
        if k not in ref:
            err.append('reference.json missing ' + k)
    for k, p in (ref.get('limits', {}).get('parameters') or {}).items():
        for jur in ('epa', 'health_canada', 'nom127'):
            if jur not in p or 'url' not in p[jur] or 'type' not in p[jur]:
                err.append('limit %s.%s lacks url/type' % (k, jur))
    for k, s in src.items():
        for f in ('name', 'publisher', 'url', 'role', 'cadence'):
            if f not in s:
                err.append('source %s missing %s' % (k, f))
    if err:
        raise ValueError('curated source validation failed: ' + '; '.join(err))


def layers_inventory():
    out, miss = [], []
    for lid, title, f, sid, prec, label, recfn, note in LAYER_DEFS:
        p = os.path.join(LAYERS, f)
        if not os.path.exists(p):
            miss.append(f)
            continue
        j = load(p)
        rec = None
        try:
            if recfn:
                rec = recfn(j)
            elif lid.startswith('wqp'):
                rec = sum((v.get('sites') or 0) for v in (j.get('summary') or {}).values()) if isinstance(j.get('summary'), dict) else None
        except Exception:
            rec = None
        out.append({'id': lid, 'title': title, 'file': 'data/layers/' + f, 'source': sid, 'precision': prec, 'label': label, 'records': rec, 'asof': _asof(j), 'size_kb': round(os.path.getsize(p) / 1024), 'note': note})
    return out, miss


def build_cop():
    snap = load(SRC + '/cop_snapshot.json')
    live = load(LAYERS + '/gdacs.json') or {}
    cop = {'meta': dict(snap['meta'], label='CURATED snapshot of prior Poseidon WATINT COP, plus LIVE GDACS events from the feed', live_gdacs_asof=live.get('asof')),
           'bluf': snap['bluf'], 'countries': snap['countries'], 'points': snap['points'], 'gdacs_snapshot': snap['gdacs'], 'signals': snap.get('signals'), 'provenance': snap.get('provenance'), 'notes': snap.get('notes'), 'headlines': snap.get('headlines'),
           'gdacs_live': live.get('events', [])}
    save(LAYERS + '/cop.json', cop, compact=True)
    save(LAYERS + '/world_110m.geojson', load(SRC + '/world_110m.geojson'), compact=True)
    return cop


GAL_PER_BBL = 42
OLY_POOL_GAL = 2500000 / 3.785411784   # 2,500 m3 minimum FINA 50 m pool
def mgal(bpd):
    return bpd * GAL_PER_BBL / 1e6


def build_flow():
    sd = load(LAYERS + '/sdwa_state.json') or {}
    mx = load(LAYERS + '/mx_plants.json') or {}
    wser = load(LAYERS + '/ca_wser.json') or {}
    npd = load(LAYERS + '/npdes_majors.json') or {}
    swd = load(LAYERS + '/tx_swd.json') or {}
    dcs = load(LAYERS + '/datacenters.json') or {}
    aq = load(LAYERS + '/mx_aquifers.geojson') or {}
    ng = load(LAYERS + '/nbga_grid.json') or {}
    dwa = load(LAYERS + '/ca_dwa.json') or {}
    # Sankey A: US community water systems (SDWIS via ECHO): source -> size class -> health-based violation flag (population served)
    fl = sd.get('flow') or []
    nodes, links = [], []
    def node(n):
        if n not in nodes:
            nodes.append(n)
        return n
    sizes = ['500 or fewer', '501 to 3,300', '3,301 to 10,000', '10,001 to 100,000', 'More than 100,000']
    agg1, agg2 = {}, {}
    for s, sz, v, n, pop in fl:
        agg1[(s, sz)] = agg1.get((s, sz), 0) + pop
        agg2[(sz, v)] = agg2.get((sz, v), 0) + pop
    for (s, sz), v in sorted(agg1.items()):
        links.append({'source': 'Source: ' + s, 'target': 'Size: ' + sz, 'value': v})
    for (sz, v), val in sorted(agg2.items()):
        links.append({'source': 'Size: ' + sz, 'target': 'ECHO flag: ' + v, 'value': val})
    sankeyA = {'title': 'US community water systems: raw-water source, system size and health-based violation flag (people served)', 'unit': 'people served', 'links': links, 'sizes': sizes,
               'source': 'sdwa', 'asof': sd.get('asof'), 'label': 'OBSERVED (EPA ECHO / SDWIS Fed); grouping by ANALYTIC ASSESSMENT',
               'note': 'SDWIS holds no treatment-plant or intake data, so the stage between source and utility is not drawn from it. Mexico (potabilization plants) and Canada (WSER) are in the chain map counts.',
               'systems': sum(x[3] for x in fl), 'population': sum(x[4] for x in fl)}
    # Produced-water arithmetic (curated primary figures, converted)
    pw = {
     'inputs': [
      {'id': 'permian_ttu', 'label': 'Permian produced water, about 20 million bbl/day (Texas Tech / TAWC, Leeds, 2025)', 'bpd': 20e6, 'src': 'ttu_leeds'},
      {'id': 'permian_b3', 'label': 'Permian produced water, about 20.7 million bpd in 2025 (B3 Insight)', 'bpd': 20.7e6, 'src': 'b3'},
      {'id': 'texas_rrc', 'label': 'Texas produced water, about 24 million bbl/day (Railroad Commission, 2025)', 'bpd': 24e6, 'src': 'rrc_pw'},
      {'id': 'texas_txpwc', 'label': 'Texas produced water, up to 25 million bbl/day (TxPWC to the Legislature, Mar 2025)', 'bpd': 25e6, 'src': 'txpwc'},
      {'id': 'recycled_ttu', 'label': 'Permian water recycled inside oil and gas operations, about 5.5 million bbl/day (Leeds, 2025)', 'bpd': 5.5e6, 'src': 'ttu_leeds'},
      {'id': 'nm_to_tx', 'label': 'Produced water moved from New Mexico to Texas for disposal, about 2.8 million bpd (B3 Insight)', 'bpd': 2.8e6, 'src': 'b3'}],
     'conversion': '1 barrel = 42 US gallons; Olympic pool = 2,500 m3 = %s US gallons (50 m minimum volume)' % format(round(OLY_POOL_GAL), ','),
    }
    for x in pw['inputs']:
        x['mgal_per_day'] = round(mgal(x['bpd']), 1)
        x['pools_per_day'] = round(mgal(x['bpd']) * 1e6 / OLY_POOL_GAL)
    dc_max_gpd = 5e6
    calc = {
     'claim_8bgd_gal': 8e9, 'claim_8bgd_bbl_per_day': round(8e9 / GAL_PER_BBL), 'claim_8bgd_pools': round(8e9 / OLY_POOL_GAL), 'ratio_claim_to_ttu': round(8e9 / (20e6 * GAL_PER_BBL), 1),
     'ttu_gal': 20e6 * GAL_PER_BBL, 'b3_gal': 20.7e6 * GAL_PER_BBL, 'tx_rrc_gal': 24e6 * GAL_PER_BBL,
     'dc_max_gal_per_day': dc_max_gpd, 'dc_max_bbl_per_day': round(dc_max_gpd / GAL_PER_BBL), 'dc_equiv_per_permian': round(20e6 * GAL_PER_BBL / dc_max_gpd),
     'net_after_recycling_bpd': 20e6 - 5.5e6, 'net_after_recycling_mgal': round(mgal(14.5e6), 1)}
    sankeyB = {'title': 'Permian produced water balance from published figures (million barrels per day)', 'unit': 'million bbl/day',
               'links': [{'source': 'Permian produced water (about 20)', 'target': 'Recycled in oil and gas operations (about 5.5)', 'value': 5.5},
                         {'source': 'Permian produced water (about 20)', 'target': 'Remainder: disposal, other (ANALYTIC: 20 minus 5.5)', 'value': 14.5}],
               'source': 'ttu_leeds', 'asof': '2025 (conference presentation)', 'label': 'OBSERVED inputs; the remainder is an ANALYTIC ASSESSMENT',
               'note': 'The outlets of the remainder (SWD, treatment for discharge or reuse) are not itemised in the figures this build could verify, so they are not drawn.'}
    # chain map counts
    gw = sum(1 for _ in [])
    chain = {'stages': [
      {'id': 'sources', 'name': 'Sources: aquifers, basins, produced water', 'items': [
        {'label': 'Mexico aquifers with DMA values', 'n': len(aq.get('features') or []), 'src': 'conagua', 'layer': 'mx_aquifers'},
        {'label': 'US brackish/fresh groundwater samples (USGS NBGA)', 'n': ng.get('samples'), 'src': 'nbga', 'layer': 'nbga_grid'},
        {'label': 'US produced-water chemistry records (USGS PWDB)', 'n': (load(LAYERS + '/pwdb_basins.json') or {}).get('records'), 'src': 'pwdb', 'layer': 'pwdb_grid'}]},
      {'id': 'treatment', 'name': 'Treatment and conveyance', 'items': [
        {'label': 'Mexico municipal potabilization plants in operation', 'n': (mx.get('totals') or {}).get('potab_plants'), 'src': 'conagua', 'layer': 'mx_plants'},
        {'label': 'Mexico wastewater plants (PTAR) listed active', 'n': (mx.get('totals') or {}).get('ptar_active'), 'src': 'conagua', 'layer': 'mx_plants'},
        {'label': 'Canada wastewater systems under WSER', 'n': wser.get('systems'), 'src': 'wser', 'layer': 'ca_wser'},
        {'label': 'US major NPDES dischargers (active)', 'n': len(npd.get('rows') or []), 'src': 'echo_npdes', 'layer': 'npdes_majors'}]},
      {'id': 'utilities', 'name': 'Utilities', 'items': [
        {'label': 'US community water systems', 'n': sum(v['cws'] for v in (sd.get('states') or {}).values()), 'src': 'echo_sdwa', 'layer': 'sdwa_county'},
        {'label': 'Canada First Nations active long-term advisories', 'n': dwa.get('active_ltdwa'), 'src': 'isc_dwa', 'layer': 'ca_dwa'}]},
      {'id': 'endusers', 'name': 'End users', 'items': [
        {'label': 'People served by US community water systems', 'n': sum(v['cws_pop'] for v in (sd.get('states') or {}).values()), 'src': 'echo_sdwa', 'layer': 'sdwa_county'}]},
      {'id': 'competing', 'name': 'Competing demand and disposal', 'items': [
        {'label': 'US data centers in the FracTracker register', 'n': dcs.get('records'), 'src': 'datacenters', 'layer': 'datacenters'},
        {'label': 'Texas injection/disposal wells (incl. EOR)', 'n': swd.get('n_injection_disposal'), 'src': 'rrc', 'layer': 'tx_swd'},
        {'label': 'Texas commercial disposal sites', 'n': swd.get('n_commercial'), 'src': 'rrc', 'layer': 'tx_swd'}]}],
      'label': 'ANALYTIC ASSESSMENT (stage assignment is the atlas\'s); counts are OBSERVED from each source'}
    return {'sankeyA': sankeyA, 'sankeyB': sankeyB, 'produced_water': pw, 'calc': calc, 'chain': chain, 'generated_at': iso(now())}


def build_findings(flow):
    F = []
    def add(id_, title, text, label, srcs, asof=None):
        F.append({'id': id_, 'title': title, 'text': text, 'label': label, 'sources': srcs, 'asof': asof})
    c = flow['calc']
    add('pw_scale', 'Permian produced water is about 0.84 to 0.87 billion gallons a day, not 8 billion',
        'Texas Tech (about 20 million bbl/day) and B3 Insight (about 20.7 million bpd for 2025) convert to %s and %s million gallons a day. The Railroad Commission puts all of Texas at about 24 million bbl/day (%s million gal/day). A figure of 8 billion gallons a day for the Permian is about %.1f times the Texas Tech number and would equal about %s Olympic pools a day; the 1,200 pools a day quoted beside it matches the lower figure (about %s pools).' %
        (format(round(mgal(20e6)), ','), format(round(mgal(20.7e6)), ','), format(round(mgal(24e6)), ','), c['ratio_claim_to_ttu'], format(c['claim_8bgd_pools'], ','), format(round(mgal(20e6) * 1e6 / OLY_POOL_GAL), ',')),
        'ANALYTIC ASSESSMENT', ['ttu_leeds', 'b3', 'rrc_pw', 'anthropocene'], '2025 figures')
    add('pw_vs_dc', 'Produced water could in principle cover many data centers, but treatment and logistics are the constraint',
        'At the upper figure of 5 million gallons a day for one large data center (EESI), the Permian volume of about 840 million gallons a day equals about %d such facilities. This ignores treatment cost, brine management, seasonality and where the water is relative to the load.' % c['dc_equiv_per_permian'],
        'ANALYTIC ASSESSMENT', ['eesi', 'ttu_leeds'], '2025 figures')
    w = load(LAYERS + '/tx_wells_grid.json')
    if w:
        t = w['totals']
        add('tx_wells', 'Texas well records: %s in the RRC layer' % format(w['records'], ','),
            'By symbol class: %s producing, %s shut-in, %s plugged, %s injection or disposal and %s other (RRC GIS symbols). The densest layer in the atlas; NM, OK, Alberta, BC and Saskatchewan are separate layers.' % tuple(format(t[k], ',') for k in ('producing', 'shut_in', 'plugged', 'injection_disposal', 'other')),
            'OBSERVED', ['rrc'], w.get('asof'))
    s = load(LAYERS + '/tx_swd.json')
    if s:
        add('tx_swd', 'Texas has %s injection/disposal well records and %s commercial disposal sites' % (format(s['n_injection_disposal'], ','), format(s['n_commercial'], ',')),
            'Counts include enhanced-oil-recovery injection, which the service does not separate from saltwater disposal. The Texas RRC layers carry no per-well volumes, so well counts are used as a proxy for produced-water handling activity (MODELED siting uses this proxy).', 'OBSERVED', ['rrc'], s.get('asof'))
    og = load(LAYERS + '/og_na_summary.json')
    if og:
        js = og['jurisdictions']
        tot_rec = sum(x['records'] or 0 for x in js)
        tot_inj = sum(x.get('injection_disposal_points') or 0 for x in js)
        add('na_wells', 'North American well layers: %s well records in %d jurisdictions' % (format(tot_rec, ','), len(js)),
            '; '.join('%s %s' % (x['name'], format(x['records'] or 0, ',')) for x in js) + '. Together they hold %s injection/disposal wells that are not abandoned (Texas counts the RRC injection layer). Mexico has no open coordinate registry reachable from this build (SENER completed-wells CSVs are denied to automated clients) and is shown only through CONAGUA water layers.' % format(tot_inj, ','),
            'OBSERVED', ['rrc', 'nm_ocd', 'ok_occ', 'ab_aer', 'bc_bcer', 'sk_er'], og.get('asof'))
        vols = [x for x in js if x.get('volume')]
        if vols:
            add('og_vol', 'Reported injection volumes: New Mexico and Oklahoma publish per-well figures, Texas does not',
                '; '.join('%s %s bbl (%s; %s wells with volume; saltwater-disposal wells alone %s bbl)' % (x['name'], format(x['volume']['total'], ','), x['volume']['kind'], format(x['volume']['wells'] or 0, ','), format(x['volume']['swd_only_total'], ',')) for x in vols)
                + '. The services do not state a unit; the magnitude (about %.1f million bbl/day for NM and %.1f million bbl/day for OK if read as barrels) is plausible for barrels (Permian produced water across Texas and New Mexico is about 20 million bbl/day per Texas Tech/TAWC), so the atlas reads them as barrels; the regulators have not confirmed the unit in the services. Totals include enhanced-oil-recovery injection unless marked saltwater disposal.' % (vols[0]['volume']['total'] / 365e6, vols[1]['volume']['total'] / 365e6 if len(vols) > 1 else 0),
                'ANALYTIC ASSESSMENT', ['nm_ocd', 'ok_occ'], og.get('asof'))
    q = load(LAYERS + '/quakes.json')
    if q:
        n = tot = 0
        mx_ = 0
        for lat, lon, cnt, mg, le in q['na_grid']:
            if 30.0 <= lat <= 33.5 and -105.0 <= lon <= -100.0:
                n += cnt
                mx_ = max(mx_, mg)
        add('seis', 'Permian-area earthquakes M2.5+ in the last five years: %s' % format(n, ','),
            'Count of USGS ComCat events in the box 30.0 to 33.5 N, 105.0 to 100.0 W (%s to %s), largest M%.1f. USGS does not label events natural or induced; published studies link Delaware Basin seismicity to disposal, but this atlas does not attribute individual events.' % (q['na_window']['from'], q['na_window']['to'], mx_),
            'ANALYTIC ASSESSMENT', ['usgs_quakes'], q.get('asof'))
    p = load(LAYERS + '/pwdb_basins.json')
    if p:
        b = [x for x in p['basins'] if x['basin'] == 'Permian']
        if b:
            b = b[0]
            add('pw_chem', 'Permian produced water median TDS is about %s mg/L' % format(b['tds_median_mgL'], ','),
                'USGS PWDB v3.0 reports %s TDS values for the Permian (10th to 90th percentile %s to %s mg/L). That is about %d times the EPA secondary limit of 500 mg/L, so reuse outside the oilfield needs desalination or blending.' % (format(b['n_tds'], ','), format(b['tds_p10_mgL'], ','), format(b['tds_p90_mgL'], ','), round(b['tds_median_mgL'] / 500)),
                'OBSERVED data; ratio is an ANALYTIC ASSESSMENT', ['pwdb', 'nbga'], p.get('asof'))
    sd = load(LAYERS + '/sdwa_state.json')
    if sd:
        st = sd['states']
        cws = sum(v['cws'] for v in st.values())
        hv = sum(v['cws_health_viol'] for v in st.values())
        pop = sum(v['cws_pop'] for v in st.values())
        small = [x for x in sd['flow'] if x[1] in ('500 or fewer', '501 to 3,300')]
        add('us_cws', 'US community water systems: %s systems serving %s people' % (format(cws, ','), format(pop, ',')),
            '%s of them (%.1f%%) carry the ECHO health-based violation flag. Systems serving 3,300 people or fewer are %.0f%% of community systems but %.1f%% of people served. The flag marks systems with violations of health-based standards, not measured exposure.' %
            (format(hv, ','), 100 * hv / max(cws, 1), 100 * sum(x[3] for x in small) / max(cws, 1), 100 * sum(x[4] for x in small) / max(pop, 1)),
            'OBSERVED; shares are an ANALYTIC ASSESSMENT', ['echo_sdwa'], sd.get('asof'))
    ws = wqp_summary()
    if ws:
        parts = []
        for k, v in ws.items():
            if v.get('sites'):
                parts.append('%s: %s sites, %s exceed the EPA reference value on a median basis' % (k, format(v['sites'], ','), format(v.get('sites_over_limit', 0), ',')))
        add('wqp', 'Water Quality Portal groundwater results since 2010 compared with EPA reference values',
            '; '.join(parts) + '. Counts are per monitoring site using the site median; sites are not a random sample of wells.', 'ANALYTIC ASSESSMENT', ['wqp'], (load(LAYERS + '/wqp_county.json') or {}).get('asof'))
    d = load(LAYERS + '/ca_dwa.json')
    if d:
        add('ca_dwa', 'Canada: %d active long-term drinking water advisories on First Nations public systems' % d['active_ltdwa'],
            '%d communities are covered by the ISC file; %d have an active advisory. Provincial and municipal advisories are not aggregated here, so this is not a national count.' % (d['communities'], len(d.get('communities_with_active') or [])), 'OBSERVED', ['isc_dwa'], d.get('asof'))
    a = load(LAYERS + '/mx_aquifers.geojson')
    if a:
        defi = [f for f in a['features'] if (f['properties'].get('deficit_hm3') or 0) < 0]
        add('mx_aq', 'Mexico: %d of %d aquifers show a negative availability (deficit)' % (len(defi), len(a['features'])),
            'Total deficit across those aquifers %s hm3 a year (CONAGUA DMA table, as published).' % format(round(-sum(f['properties']['deficit_hm3'] for f in defi)), ','), 'OBSERVED', ['conagua'], a.get('asof'))
    g = load(LAYERS + '/ggmn_global.json')
    if g:
        m = g['meta']
        tp = sorted(g['countries'].items(), key=lambda kv: -kv[1]['sites'])
        add('ggmn', 'No complete global well or sample dataset exists; IGRAC GGMN registers %s points from %d countries' % (format(m['records'], ','), len(g['countries'])),
            'The three largest contributors (%s) hold %.0f%% of the registered points. The registry is contributed by national agencies, has no chemistry values in the open feed used here, and GEMStat (UNEP) offers no public bulk API. Coverage is a floor, not a census.' % (', '.join('%s %s' % (k, format(v['sites'], ',')) for k, v in tp[:3]), 100 * sum(v['sites'] for k, v in tp[:3]) / m['records']),
            'OBSERVED; share is an ANALYTIC ASSESSMENT', ['igrac', 'gemstat'], m.get('asof'))
    t = load(LAYERS + '/siting_tx.json')
    if t:
        lv = t['longview']['cell']
        top = t['rows'][0]
        add('longview', 'Longview: this atlas\'s regional screen ranks the Longview cell %d of %s, which does not reproduce the paper\'s result' % (lv['rank'], format(t['longview']['of_cells'], ',')),
            'The MODELED regional score for the 0.25 degree cell containing Longview is %.1f (top cell %.1f). The cell has little brackish groundwater in NBGA (%.1f%% of samples), while the paper\'s Longview scenario is a site-specific design comparison of three options with its own SWUI metric. The two are not comparable and the model was not tuned to match the paper. The paper\'s full text was not accessed.' % (lv['score'], top[2], lv['brackish_pct']),
            'MODELED', ['paper', 'ut_news', 'nbga', 'pwdb', 'rrc'], t.get('asof'))
    dc = load(LAYERS + '/datacenters.json')
    if dc:
        tx = [r for r in dc['rows'] if r.get('state') == 'TX']
        add('dc', 'Data center register: %s US records, %d in Texas' % (format(dc['records'], ','), len(tx)),
            'Status mix (US): %s. The register is third-party compiled and carries no water-use data; cooling type is recorded for %d US records.' % (', '.join('%s %d' % (k, v) for k, v in sorted(dc['by_status'].items(), key=lambda kv: -kv[1])[:4]), sum(1 for r in dc['rows'] if r.get('cooling_type') or r.get('cooling_source'))),
            'OBSERVED', ['datacenters'], dc.get('asof'))
    return F


def build(feed_meta=None):
    ref = load(SRC + '/reference.json')
    src = load(SRC + '/sources.json')
    validate(ref, src)
    cop = build_cop()
    flow = build_flow()
    save(DATA + '/flow.json', flow)
    findings = build_findings(flow)
    save(DATA + '/findings.json', findings)
    inv, miss = layers_inventory()
    asof_by_layer = {x['id']: x['asof'] for x in inv}
    reg = {}
    for k, s in src.items():
        d = dict(s)
        ly = [x for x in inv if x['source'] == k]
        d['asof'] = next((x['asof'] for x in ly if x['asof']), None)
        d['records'] = next((x['records'] for x in ly if x['records']), None)
        reg[k] = d
    save(DATA + '/sources.json', reg)
    old = load(DATA + '/meta.json', {}) or {}
    meta = {'brand': ref['brand'], 'datum': ref['datum'], 'precision': ref['precision'], 'labels': ref['labels'], 'footer': ref['footer'], 'built_at': iso(now()),
            'feeds': feed_meta if feed_meta is not None else old.get('feeds', {}), 'layers': inv, 'missing_layers': miss}
    save(DATA + '/meta.json', meta)
    upd = load(DATA + '/updates.json', {'items': []}) or {'items': []}
    rev = load(DATA + '/review.json', {'items': []}) or {'items': []}
    bundle = {'ref': ref, 'meta': meta, 'sources': reg, 'flow': flow, 'findings': findings,
              'updates': upd.get('items', [])[:400], 'updates_generated_at': upd.get('generated_at'), 'review': rev.get('items', []),
              'pwdb_basins': (load(LAYERS + '/pwdb_basins.json') or {}).get('basins', []),
              'sdwa_state': (load(LAYERS + '/sdwa_state.json') or {}).get('states', {}),
              'aqueduct': load(SRC + '/aqueduct_province_bws.json'), 'reel_check': load(SRC + '/reel_check.json')}
    js = '/* generated by scripts/pipeline.py: do not edit */\nwindow.WT = ' + json.dumps(bundle, ensure_ascii=False, separators=(',', ':')) + ';\n'
    open(os.path.join(ROOT, 'assets/js/data.js'), 'w', encoding='utf-8').write(js)
    log('build: %d layers, %d sources, %d findings, bundle %d KB' % (len(inv), len(reg), len(findings), len(js) // 1024))
    return meta
