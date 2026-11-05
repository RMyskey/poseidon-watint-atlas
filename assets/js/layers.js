/* Poseidon NARINT WATINT atlas: main-map layer registry and click handlers. */
(function () {
  'use strict';
  var U = window.WTU, D = U.D, REF = D.ref, esc = U.esc;
  var A = window.WTApp = { LAYERS: [], H: {}, DAT: {}, map: null };
  var H = A.H, LAYERS = A.LAYERS;
  function row(k, v) { return v === null || v === undefined || v === '' ? '' : [k, v]; }
  var DC_COL = { 'Operating': '#3ddc97', 'Proposed': '#38c7ff', 'Approved/Permitted/Under construction': '#f2b84b', 'Expanding': '#5b8def', 'Suspended': '#ff9f43', 'Cancelled': '#7d8aa3', 'Pre-proposal': '#b06cff' };
  var CAT_COL = { flood: '#38c7ff', drought: '#ff9f43', energy: '#f2b84b', food: '#3ddc97', displacement: '#b06cff', conflict: '#ff5c6c' };
  var DM_COL = ['#ffe36e', '#fcd37f', '#ffaa00', '#e60000', '#730000'];
  var TDS_B = [10000, 50000, 100000, 150000, 200000];
  var TDS_C = ['#2397a8', '#4cc39a', '#b6e37a', '#ffd37a', '#ff9f43', '#ff5c6c'];
  A.TDS_B = TDS_B; A.TDS_C = TDS_C; A.DC_COL = DC_COL;
  var fmtMg = function (v) { return U.n(v) + ' mg/L'; };

  H.cop_ctry = function (p) {
    var c = D.cop_c && D.cop_c[p.iso];
    if (!c) return { title: p.name, kick: 'Country (no COP record)', rows: [], label: 'CURATED' };
    var gk = c.gk || {};
    return { title: c.name, kick: 'WATINT COP country record', label: 'CURATED', src: 'cop', asof: 'Oct 23, 2026 snapshot', prec: 'C',
      rows: [row('Composite threat index (CTI)', c.cti), row('Aqueduct baseline water stress', c.bws), row('INFORM risk', c.inform), row('IPC Phase 3+ people', c.ipcPop ? U.n(c.ipcPop) + ' (to ' + c.ipcTo + ')' : null),
        row('Forcibly displaced', c.disp ? U.n(c.disp) : null), row('GDELT water-theme articles (7 d)', gk.all), row('Of which drought / flood / conflict', [gk.dr, gk.fl, gk.co].join(' / ')), row('GDACS alerts', c.alerts)] };
  };
  H.cop_pts = function (p) {
    var arts = [], cats = {};
    try { arts = JSON.parse(p.arts || '[]'); } catch (e) { arts = []; }
    try { cats = JSON.parse(p.cats || '{}'); } catch (e) { cats = {}; }
    return { title: p.name, kick: 'News cluster (GDELT GKG, Oct 16 to 23)', label: 'CURATED', src: 'cop', asof: 'Oct 23, 2026 snapshot', prec: 'E',
      rows: [row('Articles', p.n), row('Themes', Object.keys(cats).map(function (k) { return k + ' ' + cats[k]; }).join(', '))],
      html: arts.slice(0, 5).map(function (a) { return '<div class="d-intel"><a href="' + esc(a[1]) + '" target="_blank" rel="noopener">' + esc(a[0]) + '</a><small>' + esc(a[2]) + ' · ' + esc(a[3]) + '</small></div>'; }).join('') };
  };
  H.gdacs = function (p) { return { title: p.name || p.id, kick: 'GDACS ' + p.type + ' · ' + p.alert + ' alert', label: 'OBSERVED', src: 'gdacs', asof: p.asof, prec: 'E',
    rows: [row('Countries', p.country), row('From', U.date(p.from)), row('To', U.date(p.to)), row('Severity', p.severity)], links: [['GDACS report', p.url]] }; };
  H.usdm = function (p) { return { title: 'US Drought Monitor ' + p.label, kick: 'Weekly drought class', label: 'OBSERVED', src: 'usdm', asof: U.asofOf('usdm'), prec: 'C', rows: [row('Class', p.label)] }; };
  H.quakes_recent = function (p) { return { title: 'M' + p.mag + ' ' + p.place, kick: 'USGS earthquake', label: 'OBSERVED', src: 'usgs_quakes', asof: p.time, prec: 'F', rows: [row('Depth', p.depth + ' km'), row('Time', p.time)], links: [['USGS event', 'https://earthquake.usgs.gov/earthquakes/eventpage/' + p.id]] }; };
  H.quakes_na = function (p) { return { title: 'Earthquake cell ' + p.lat + ', ' + p.lon, kick: 'M2.5+ events in 5 years, 0.5° cell', label: 'OBSERVED', src: 'usgs_quakes', asof: U.asofOf('quakes'), prec: 'G',
    rows: [row('Events M2.5+', p.n), row('Largest magnitude', p.max), row('Latest event', U.date(p.last * 1000))], note: 'USGS does not label events as natural or induced.' }; };
  H.wells = function (p) { return { title: 'Texas well cell ' + p.lat + ', ' + p.lon, kick: 'Wells per 0.1° cell (RRC)', label: 'OBSERVED', src: 'rrc', asof: U.asofOf('tx_wells_grid'), prec: 'G',
    rows: [row('Producing', U.n(p.producing)), row('Shut-in', U.n(p.shut_in)), row('Plugged', U.n(p.plugged)), row('Injection / disposal', U.n(p.inj)), row('Other', U.n(p.other))] }; };
  H.swd = function (p) { return { title: p.kind === 'com' ? 'Commercial disposal site' : 'Injection / disposal well', kick: 'Texas RRC record', label: 'OBSERVED', src: 'rrc', asof: U.asofOf('tx_swd'), prec: 'F',
    rows: [], note: 'The service layer carries location only; EOR injection and saltwater disposal are not separated. No volume is published here.' }; };
  H.pwdb = function (p) { return { title: 'Produced water cell ' + p.lat + ', ' + p.lon, kick: 'USGS PWDB, 0.25° cell', label: 'OBSERVED', src: 'pwdb', asof: U.asofOf('pwdb_grid'), prec: 'G',
    rows: [row('Samples with TDS', U.n(p.n)), row('Median TDS', fmtMg(p.med)), row('Maximum TDS', fmtMg(p.max)), row('Ratio to EPA 500 mg/L SMCL', U.n(p.med / 500, 0) + '×  (ANALYTIC ASSESSMENT)')] }; };
  H.nbga = function (p) { return { title: 'Groundwater salinity cell ' + p.lat + ', ' + p.lon, kick: 'USGS NBGA, 0.25° cell (samples to 2013)', label: 'OBSERVED', src: 'nbga', asof: U.asofOf('nbga_grid'), prec: 'G',
    rows: [row('Samples', U.n(p.n)), row('Median TDS', fmtMg(p.med)), row('Fresh <1,000 mg/L', p.fresh + '%'), row('Brackish 1,000 to 10,000', p.brk + '%'), row('Saline >10,000', p.sal + '%'), row('Median depth', p.depth !== null && p.depth !== undefined ? U.n(p.depth) + ' ft' : null)] }; };
  H.sdwa = function (p) { return { title: p.name + ', ' + p.state, kick: 'Community water systems (SDWIS via ECHO)', label: 'OBSERVED', src: 'echo_sdwa', asof: U.asofOf('sdwa_county'), prec: 'C',
    rows: [row('Community systems', U.n(p.cws)), row('Population served (summed)', U.n(p.pop)), row('With health-based violation flag', U.n(p.hv) + (p.cws ? ' (' + (100 * p.hv / p.cws).toFixed(1) + '%)' : '')), row('Serious violators', U.n(p.ser))],
    note: 'A system is counted in every county it serves, so population can be counted more than once. The flag marks violations of health-based standards, not exposure.' }; };
  H.ca_dwa = function (p) { return { title: p.community, kick: 'Long-term drinking water advisory · ' + p.status, label: 'OBSERVED', src: 'isc_dwa', asof: U.asofOf('ca_dwa'), prec: 'F',
    rows: [row('System', p.system), row('Province/region', p.region), row('Advisory', p.type), row('Advisory since', p.set), row('Population band', p.pop), row('Expected lift', p.expected), row('Corrective measure', p.measure), row('Project phase', p.phase)] }; };
  H.mx_aq = function (p) { return { title: p.name + ' (' + p.state + ')', kick: 'Mexico aquifer availability', label: 'OBSERVED', src: 'conagua', asof: U.asofOf('mx_aquifers'), prec: 'C',
    rows: [row('Region', p.region), row('Area', U.n(p.area_km2) + ' km²'), row('Recharge', U.n(p.recharge_hm3, 1) + ' hm³/yr'), row('Concessioned', U.n(p.concessioned_hm3, 1) + ' hm³/yr'), row('Availability (DMA > 0)', U.n(p.avail_hm3, 1) + ' hm³/yr'), row('Deficit (DMA < 0)', U.n(p.deficit_hm3, 1) + ' hm³/yr')] }; };
  H.mx_q = function (p) {
    var nom = REF.limits.parameters, rows = [row('Type', p.t === 'gw' ? 'Groundwater' : 'Surface water'), row('State / municipality', p.st + ' / ' + p.mun), row('Aquifer', p.aq), row('Year', p.yr), row('CONAGUA flag', p.flag)];
    function cmp(label, v, par, unit) { if (v === null || v === undefined || v === '') return ''; var lim = nom[par].nom127.value; return row(label, U.sig(v) + ' ' + unit + (lim !== null ? '  (NOM-127: ' + lim + (v > lim ? ', above' : ', below') + ')' : '')); }
    rows.push(cmp('TDS', p.tds, 'tds', 'mg/L'), cmp('Nitrate as N', p.no3n, 'nitrate', 'mg/L'));
    if (p.as_mgL !== undefined && p.as_mgL !== '' && p.as_mgL !== null) rows.push(row('Arsenic', U.sig(p.as_mgL * 1000) + ' µg/L  (NOM-127: 10' + (p.as_mgL * 1000 > 10 ? ', above' : ', below') + ')'));
    return { title: p.n, kick: 'CONAGUA RNMCA monitoring site', label: 'OBSERVED', src: 'conagua', asof: U.asofOf('mx_quality_sites'), prec: 'M', rows: rows,
      note: 'Compared with the NOM-127-SSA1-2021 limit values in data/source/reference.json. Reference comparison only.' };
  };
  H.mx_piezo = function () { return { title: 'Piezometric network station', kick: 'CONAGUA', label: 'OBSERVED', src: 'conagua', asof: U.asofOf('mx_piezo'), prec: 'M', rows: [], note: 'Location only; depth series are in the CONAGUA file.' }; };
  H.npdes = function (p) { return { title: p.name, kick: (p.potw ? 'Major municipal (POTW)' : 'Major industrial') + ' NPDES permit · ' + p.st, label: 'OBSERVED', src: 'echo_npdes', asof: U.asofOf('npdes_majors'), prec: 'F',
    rows: [row('Permit', p.id), row('County', p.county), row('Design flow', p.design !== null && p.design !== undefined && p.design !== 'null' ? U.n(p.design, 2) + ' MGD' : null), row('Actual average flow', p.actual !== null && p.actual !== undefined && p.actual !== 'null' ? U.n(p.actual, 2) + ' MGD' : null), row('Compliance status', p.status || 'none reported')],
    links: [['EPA ECHO facility report', 'https://echo.epa.gov/detailed-facility-report?fid=' + encodeURIComponent(p.id)]] }; };
  H.wser = function (p) { return { title: p.system, kick: 'WSER wastewater system · ' + p.province, label: 'OBSERVED', src: 'wser', asof: U.asofOf('ca_wser'), prec: 'F',
    rows: [row('Owner', p.owner), row('City', p.city), row('Average daily effluent', U.n(p.vol, 0) + ' m³/day'), row('Discharge', p.kind), row('Treatment', p.treat), row('Status', p.status)] }; };
  H.ggmn = function (p) { return { title: 'GGMN cell ' + p.lat + ', ' + p.lon, kick: 'IGRAC monitoring points, 1° cell', label: 'OBSERVED', src: 'igrac', asof: U.asofOf('ggmn_global'), prec: 'G',
    rows: [row('Registered points', U.n(p.sites)), row('With level series', U.n(p.lv)), row('With quality series', U.n(p.ql))], note: 'A registry of contributed points; not a complete inventory.' }; };
  H.dcs = function (p) { return { title: p.name, kick: 'Data center · ' + p.status, label: 'OBSERVED', src: 'datacenters', asof: U.asofOf('datacenters'), prec: 'A',
    rows: [row('Location', [p.city, p.county, p.state].filter(Boolean).join(', ')), row('Operator', p.operator), row('Tenant', p.tenant), row('Capacity', p.mw), row('Cooling', p.cooling), row('Location confidence', p.conf), row('Updated', p.updated)],
    note: 'Third-party compiled register; no water-use figures are published for these records.' }; };
  H.siting = function (p) { return { title: 'Siting cell ' + p.lat + ', ' + p.lon + ' · rank ' + p.rank, kick: 'MODELED screening score (default weights)', label: 'MODELED', src: 'paper', asof: U.asofOf('siting_tx'), prec: 'G',
    rows: [row('Score', p.score), row('Brackish groundwater', p.sb), row('Produced-water presence', p.sp), row('Water stress', p.ss), row('Demand', p.sd), row('NBGA brackish share', p.bp + '%'), row('Injection/disposal wells within 50 km', U.n(p.swd)), row('Data centers within 50 km', p.dc)],
    note: 'Not the SWUI of the published paper. Adjust weights in the Siting dashboard.' }; };
  H.longview = function () { return { title: 'Longview, Texas (callout)', kick: 'Location named in the UT Austin paper', label: 'ANALYTIC ASSESSMENT', src: 'paper', asof: 'paper online 2026-08-17', prec: 'A',
    rows: [row('Coordinate', '32.5007, -94.7405 (city centroid)')], note: 'See the Siting dashboard for this atlas\'s own screening score and why it does not reproduce the paper\'s case study.' }; };

  function circ(id, src, wt, paint, extra) { var l = { id: id, type: 'circle', source: src, paint: paint, metadata: { wt: wt } }; if (extra) for (var k in extra) l[k] = extra[k]; return l; }
  function add(srcs, layers) {
    var map = A.map;
    Object.keys(srcs).forEach(function (k) { if (!map.getSource(k)) map.addSource(k, srcs[k]); else map.getSource(k).setData(srcs[k].data); });
    layers.forEach(function (l) { if (!map.getLayer(l.id)) map.addLayer(l, 'sel-halo'); });
  }
  function reg(o) { LAYERS.push(o); return o; }
  var fc = U.fc, pt = U.pt;

  reg({ id: 'cop_ctry', grp: 'Hazards and global COP', label: 'Threat index by country (COP snapshot)', tag: 'CURATED', on: true, ids: ['cop-fill', 'cop-line'], hi: ['cop-fill'],
    load: function () { return Promise.all([U.layer('cop.json'), U.layer('world_110m.geojson')]); },
    build: function (d) {
      var cop = d[0], w = JSON.parse(JSON.stringify(d[1])); D.cop_c = cop.countries; A.DAT.cop = cop;
      w.features.forEach(function (f) { var c = cop.countries[f.properties.iso]; f.properties.cti = c && c.cti !== undefined ? c.cti : null; });
      add({ cop_w: { type: 'geojson', data: w } }, [
        { id: 'cop-fill', type: 'fill', source: 'cop_w', metadata: { wt: 'cop_ctry' }, paint: { 'fill-color': ['case', ['==', ['get', 'cti'], null], 'rgba(0,0,0,0)', U.stepExpr('cti', [20, 30, 40, 50, 60], U.HOT)], 'fill-opacity': 0.38 } },
        { id: 'cop-line', type: 'line', source: 'cop_w', paint: { 'line-color': '#7f93b5', 'line-width': 0.5, 'line-opacity': 0.55 } }]);
    },
    legend: function () { return U.legendSteps('Composite threat index (0 to 100)', [20, 30, 40, 50, 60], U.HOT, String, 'CURATED'); } });
  reg({ id: 'cop_pts', grp: 'Hazards and global COP', label: 'Water-news clusters (GDELT GKG, Oct 16 to 23)', tag: 'CURATED', ids: ['cop-pts'], hi: ['cop-pts'],
    load: function () { return U.layer('cop.json'); },
    build: function (cop) {
      var f = cop.points.map(function (p) { var dom = Object.keys(p.cats || {}).sort(function (a, b) { return p.cats[b] - p.cats[a]; })[0] || 'flood'; return pt(p.lon, p.lat, { name: p.name, n: p.n, dom: dom, cats: JSON.stringify(p.cats || {}), arts: JSON.stringify(p.arts || []) }); });
      add({ cop_p: { type: 'geojson', data: fc(f) } }, [circ('cop-pts', 'cop_p', 'cop_pts', { 'circle-radius': ['interpolate', ['linear'], ['get', 'n'], 1, 3, 20, 5, 100, 9, 500, 15], 'circle-color': ['match', ['get', 'dom'], 'flood', CAT_COL.flood, 'drought', CAT_COL.drought, 'energy', CAT_COL.energy, 'food', CAT_COL.food, 'displacement', CAT_COL.displacement, 'conflict', CAT_COL.conflict, '#7d8aa3'], 'circle-opacity': 0.75, 'circle-stroke-width': 0.8, 'circle-stroke-color': '#06101c' })]);
    },
    legend: function () { return '<div class="lg-t">News clusters by dominant theme ' + U.lbl('CURATED') + '</div><div class="lg-grid">' + Object.keys(CAT_COL).map(function (k) { return '<div class="lg-row"><span class="lg-sw" style="background:' + CAT_COL[k] + '"></span>' + k + '</div>'; }).join('') + '</div>'; } });
  reg({ id: 'gdacs', grp: 'Hazards and global COP', label: 'GDACS drought, flood, cyclone events (21 d)', tag: 'OBSERVED', on: true, ids: ['gdacs-pts'], hi: ['gdacs-pts'], note: 'Refreshed by the daily pipeline (GDACS blocks browser requests).',
    load: function () { return U.layer('gdacs.json'); },
    build: function (g) {
      var f = g.events.map(function (e) { return pt(e.lon, e.lat, { id: e.id, type: e.type, alert: e.alert, name: e.name, country: e.country, from: e.from, to: e.to, severity: e.severity, url: e.url, asof: g.asof }); });
      add({ gd: { type: 'geojson', data: fc(f) } }, [circ('gdacs-pts', 'gd', 'gdacs', { 'circle-radius': ['match', ['get', 'alert'], 'Red', 9, 'Orange', 7, 5], 'circle-color': ['match', ['get', 'alert'], 'Red', '#ff3b4e', 'Orange', '#ff9f43', '#3ddc97'], 'circle-opacity': 0.85, 'circle-stroke-width': 2, 'circle-stroke-color': ['match', ['get', 'type'], 'DR', '#f2b84b', 'FL', '#38c7ff', '#ffffff'] })]);
    },
    legend: function () { return '<div class="lg-t">GDACS alert ' + U.lbl('OBSERVED') + '</div><div class="lg-grid"><div class="lg-row"><span class="lg-sw" style="background:#ff3b4e"></span>Red</div><div class="lg-row"><span class="lg-sw" style="background:#ff9f43"></span>Orange</div><div class="lg-row"><span class="lg-sw" style="background:#3ddc97"></span>Green</div></div><div class="lg-row small">Ring: gold = drought, blue = flood, white = cyclone</div>'; } });
  reg({ id: 'usdm', grp: 'Hazards and global COP', label: 'US Drought Monitor (weekly)', tag: 'OBSERVED', on: true, ids: ['usdm-fill'], hi: ['usdm-fill'],
    load: function () { return U.layer('usdm.geojson'); },
    build: function (g) { add({ usdm: { type: 'geojson', data: g } }, [{ id: 'usdm-fill', type: 'fill', source: 'usdm', metadata: { wt: 'usdm' }, paint: { 'fill-color': ['match', ['get', 'dm'], 0, DM_COL[0], 1, DM_COL[1], 2, DM_COL[2], 3, DM_COL[3], DM_COL[4]], 'fill-opacity': 0.3 } }]); },
    legend: function () { return '<div class="lg-t">Drought class ' + U.lbl('OBSERVED') + '</div><div class="lg-grid">' + ['D0', 'D1', 'D2', 'D3', 'D4'].map(function (k, i) { return '<div class="lg-row"><span class="lg-sw" style="background:' + DM_COL[i] + ';border-radius:3px"></span>' + k + '</div>'; }).join('') + '</div>'; } });
  reg({ id: 'quakes_recent', grp: 'Hazards and global COP', label: 'USGS earthquakes M4.5+ (30 d)', tag: 'OBSERVED', ids: ['q-recent'], hi: ['q-recent'], note: 'Fetched live from USGS when online; else the pipeline snapshot.',
    load: function () {
      var live = window.WT_CONFIG && window.WT_CONFIG.liveFeeds;
      var t0 = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10);
      var snap = U.layer('quakes.json').then(function (q) { return { src: 'pipeline snapshot', asof: q.asof, rows: q.recent_m45_30d.map(function (r) { return { lon: r[0], lat: r[1], mag: r[2], time: new Date(r[3] * 1000).toISOString().slice(0, 16).replace('T', ' ') + ' UTC', depth: r[4], place: r[5], id: r[6] }; }) }; });
      if (!live) return snap;
      var ctl = new AbortController(); var to = setTimeout(function () { ctl.abort(); }, 7000);
      return fetch('https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&minmagnitude=4.5&orderby=time&limit=1000&starttime=' + t0, { signal: ctl.signal }).then(function (r) { clearTimeout(to); if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (j) { return { src: 'LIVE USGS', asof: new Date().toISOString(), rows: j.features.map(function (f) { return { lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1], mag: f.properties.mag, time: new Date(f.properties.time).toISOString().slice(0, 16).replace('T', ' ') + ' UTC', depth: f.geometry.coordinates[2], place: f.properties.place, id: f.id }; }) }; })
        .catch(function () { return snap; });
    },
    build: function (q) {
      this.dataNote = q.src + ' · ' + U.stamp(q.asof);
      add({ qr: { type: 'geojson', data: fc(q.rows.map(function (r) { return pt(r.lon, r.lat, r); })) } }, [circ('q-recent', 'qr', 'quakes_recent', { 'circle-radius': ['interpolate', ['linear'], ['get', 'mag'], 4.5, 3, 6, 7, 8, 16], 'circle-color': '#ff7a59', 'circle-opacity': 0.55, 'circle-stroke-color': '#ffd0c4', 'circle-stroke-width': 1 })]);
    },
    legend: function () { return '<div class="lg-t">Earthquakes M4.5+, 30 d ' + U.lbl('OBSERVED') + '</div><div class="lg-row"><span class="lg-sw" style="background:#ff7a59"></span>Size follows magnitude' + (this.dataNote ? ' · ' + esc(this.dataNote) : '') + '</div>'; } });
  reg({ id: 'quakes_na', grp: 'Oil and gas', label: 'North America M2.5+ earthquakes, 5 y (0.5° cells)', tag: 'OBSERVED', ids: ['q-na'], hi: ['q-na'],
    load: function () { return U.layer('quakes.json'); },
    build: function (q) {
      var f = q.na_grid.map(function (r) { return pt(r[1], r[0], { lat: r[0], lon: r[1], n: r[2], max: r[3], last: r[4] }); });
      add({ qna: { type: 'geojson', data: fc(f) } }, [circ('q-na', 'qna', 'quakes_na', { 'circle-radius': ['interpolate', ['linear'], ['get', 'n'], 1, 2.5, 10, 5, 100, 10, 1000, 18], 'circle-color': U.stepExpr('max', [3, 3.5, 4, 5], ['#7d8aa3', '#ffd37a', '#ff9f43', '#ff5c6c', '#ff2d55']), 'circle-opacity': 0.55, 'circle-stroke-width': 0.6, 'circle-stroke-color': '#06101c' })]);
    },
    legend: function () { return U.legendSteps('Largest event in cell (M)', [3, 3.5, 4, 5], ['#7d8aa3', '#ffd37a', '#ff9f43', '#ff5c6c', '#ff2d55'], String, 'OBSERVED') + '<div class="lg-row small">Size follows event count. USGS does not label natural vs induced.</div>'; } });
  reg({ id: 'wells', grp: 'Oil and gas', label: 'Texas wells density (RRC, 0.1° cells)', tag: 'OBSERVED', ids: ['wells-heat', 'wells-c'], hi: ['wells-c'],
    load: function () { return U.layer('tx_wells_grid.json'); },
    build: function (g) {
      var f = g.rows.map(function (r) { var tot = r[2] + r[3] + r[4] + r[5] + r[6]; return pt(r[1], r[0], { lat: r[0], lon: r[1], producing: r[2], shut_in: r[3], plugged: r[4], inj: r[5], other: r[6], tot: tot }); });
      add({ wl: { type: 'geojson', data: fc(f) } }, [
        { id: 'wells-heat', type: 'heatmap', source: 'wl', maxzoom: 9, paint: { 'heatmap-weight': ['interpolate', ['linear'], ['get', 'tot'], 0, 0, 500, 0.6, 3000, 1], 'heatmap-intensity': 1.2, 'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 3, 9, 8, 30], 'heatmap-opacity': 0.75, 'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, 'rgba(0,0,0,0)', 0.2, 'rgba(60,30,120,0.6)', 0.45, 'rgb(190,50,130)', 0.7, 'rgb(250,140,60)', 1, 'rgb(255,245,170)'] } },
        circ('wells-c', 'wl', 'wells', { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 3, 10, 12], 'circle-color': ['interpolate', ['linear'], ['get', 'tot'], 0, '#2b1a4f', 400, '#c0398b', 1500, '#ffb547', 4000, '#fff3a8'], 'circle-opacity': 0.5, 'circle-stroke-width': 0.4, 'circle-stroke-color': '#06101c' }, { minzoom: 6.5 })]);
    },
    legend: function () { return '<div class="lg-t">Texas well records per 0.1° cell ' + U.lbl('OBSERVED') + '</div><div class="lg-grad" style="background:linear-gradient(90deg,#3c1e78,#be3282,#fa8c3c,#fff5aa)"></div><div class="lg-ticks"><span>few</span><span>1,500+</span><span>4,000+</span></div>'; } });
  reg({ id: 'swd', grp: 'Oil and gas', label: 'Texas injection/disposal wells and commercial disposal', tag: 'OBSERVED', ids: ['swd-i', 'swd-c'], hi: ['swd-i', 'swd-c'],
    load: function () { return U.layer('tx_swd.json'); },
    build: function (g) {
      var a = g.injection_disposal.map(function (p) { return pt(p[0], p[1], { kind: 'swd' }); }), b = g.commercial_disposal.map(function (p) { return pt(p[0], p[1], { kind: 'com' }); });
      add({ swd1: { type: 'geojson', data: fc(a) }, swd2: { type: 'geojson', data: fc(b) } }, [
        circ('swd-i', 'swd1', 'swd', { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 1.2, 10, 4], 'circle-color': '#38c7ff', 'circle-opacity': 0.55 }),
        circ('swd-c', 'swd2', 'swd', { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 3, 10, 7], 'circle-color': '#ff5c6c', 'circle-opacity': 0.9, 'circle-stroke-width': 1, 'circle-stroke-color': '#fff' })]);
    },
    legend: function () { return '<div class="lg-t">Disposal ' + U.lbl('OBSERVED') + '</div><div class="lg-row"><span class="lg-sw" style="background:#38c7ff"></span>Injection / disposal well</div><div class="lg-row"><span class="lg-sw" style="background:#ff5c6c"></span>Commercial disposal site</div>'; } });
  reg({ id: 'pwdb', grp: 'Oil and gas', label: 'Produced-water salinity (USGS PWDB, 0.25° cells)', tag: 'OBSERVED', ids: ['pwdb-c'], hi: ['pwdb-c'],
    load: function () { return U.layer('pwdb_grid.json'); },
    build: function (g) {
      var f = g.rows.map(function (r) { return pt(r[1], r[0], { lat: r[0], lon: r[1], n: r[2], med: r[3], max: r[4] }); });
      add({ pw: { type: 'geojson', data: fc(f) } }, [circ('pwdb-c', 'pw', 'pwdb', { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 2.5, 8, 9], 'circle-color': U.stepExpr('med', TDS_B, TDS_C), 'circle-opacity': 0.8, 'circle-stroke-width': 0.4, 'circle-stroke-color': '#06101c' })]);
    },
    legend: function () { return U.legendSteps('Median TDS (mg/L)', TDS_B, TDS_C, U.n, 'OBSERVED'); } });
  reg({ id: 'nbga', grp: 'Oil and gas', label: 'Brackish groundwater share (USGS NBGA)', tag: 'OBSERVED', ids: ['nbga-c'], hi: ['nbga-c'],
    load: function () { return U.layer('nbga_grid.json'); },
    build: function (g) {
      var f = g.rows.map(function (r) { return pt(r[1], r[0], { lat: r[0], lon: r[1], n: r[2], med: r[3], brk: r[4], fresh: r[5], sal: r[6], depth: r[7] }); });
      add({ nb: { type: 'geojson', data: fc(f) } }, [circ('nbga-c', 'nb', 'nbga', { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 2, 8, 8], 'circle-color': U.stepExpr('brk', [10, 30, 50, 75], ['#16365e', '#1f6390', '#2397a8', '#4cc39a', '#fff27a']), 'circle-opacity': 0.7 })]);
    },
    legend: function () { return U.legendSteps('Brackish share of samples (%)', [10, 30, 50, 75], ['#16365e', '#1f6390', '#2397a8', '#4cc39a', '#fff27a'], String, 'OBSERVED'); } });
  reg({ id: 'sdwa', grp: 'Water supply', label: 'US community water systems by county (health-flag share)', tag: 'OBSERVED', ids: ['sdwa-fill'], hi: ['sdwa-fill'],
    load: function () { return Promise.all([U.layer('us_counties.geojson'), U.layer('sdwa_county.json')]); },
    build: function (d) {
      var g = JSON.parse(JSON.stringify(d[0])), c = d[1].counties;
      g.features.forEach(function (f) { var r = c[f.properties.fips], p = f.properties; if (r) { p.cws = r[0]; p.pop = r[1]; p.hv = r[2]; p.ser = r[3]; p.pct = r[0] >= 3 ? 100 * r[2] / r[0] : null; } else { p.cws = 0; p.pct = null; } });
      add({ sd: { type: 'geojson', data: g } }, [{ id: 'sdwa-fill', type: 'fill', source: 'sd', metadata: { wt: 'sdwa' }, paint: { 'fill-color': ['case', ['==', ['get', 'pct'], null], 'rgba(0,0,0,0)', U.stepExpr('pct', [0.01, 5, 10, 20, 35], ['#1a2d46', '#2a6f9a', '#4cc39a', '#ffd37a', '#ff9f43', '#ff5c6c'])], 'fill-opacity': 0.62, 'fill-outline-color': 'rgba(120,150,190,.35)' } }]);
    },
    legend: function () { return U.legendSteps('Share of community systems flagged (%)', [0.01, 5, 10, 20, 35], ['#1a2d46', '#2a6f9a', '#4cc39a', '#ffd37a', '#ff9f43', '#ff5c6c'], String, 'OBSERVED') + '<div class="lg-row small">Counties with fewer than 3 systems are not shaded.</div>'; } });
  reg({ id: 'ca_dwa', grp: 'Water supply', label: 'Canada First Nations drinking water advisories', tag: 'OBSERVED', ids: ['dwa-pts'], hi: ['dwa-pts'],
    load: function () { return U.layer('ca_dwa.json'); },
    build: function (g) {
      var f = g.active.map(function (a) { return pt(a.lon, a.lat, { community: a.community, system: a.system, region: a.region, type: a.type, set: a.set, pop: a.pop, expected: a.expected, measure: a.measure, phase: a.phase, status: 'active' }); });
      add({ dwa: { type: 'geojson', data: fc(f) } }, [circ('dwa-pts', 'dwa', 'ca_dwa', { 'circle-radius': 6, 'circle-color': '#ff5c6c', 'circle-opacity': 0.9, 'circle-stroke-width': 1.4, 'circle-stroke-color': '#fff' })]);
    },
    legend: function () { return '<div class="lg-t">Canada (on-reserve public systems) ' + U.lbl('OBSERVED') + '</div><div class="lg-row"><span class="lg-sw" style="background:#ff5c6c"></span>Active long-term advisory</div>'; } });
  reg({ id: 'mx_aq', grp: 'Water supply', label: 'Mexico aquifer availability (deficit shading)', tag: 'OBSERVED', ids: ['mxaq-fill', 'mxaq-line'], hi: ['mxaq-fill'],
    load: function () { return U.layer('mx_aquifers.geojson'); },
    build: function (g) { add({ mxaq: { type: 'geojson', data: g } }, [
      { id: 'mxaq-fill', type: 'fill', source: 'mxaq', metadata: { wt: 'mx_aq' }, paint: { 'fill-color': U.stepExpr('deficit_hm3', [-100, -10, -0.001], ['#ff2d55', '#ff5c6c', '#ff9f43', '#2a6f6a']), 'fill-opacity': 0.5 } },
      { id: 'mxaq-line', type: 'line', source: 'mxaq', paint: { 'line-color': '#9fb6d8', 'line-width': 0.4, 'line-opacity': 0.5 } }]); },
    legend: function () { return '<div class="lg-t">Aquifer DMA (hm³/yr) ' + U.lbl('OBSERVED') + '</div>' + [['#ff2d55', 'Deficit beyond -100'], ['#ff5c6c', 'Deficit -100 to -10'], ['#ff9f43', 'Deficit -10 to 0'], ['#2a6f6a', 'Availability ≥ 0']].map(function (x) { return '<div class="lg-row"><span class="lg-sw" style="background:' + x[0] + ';border-radius:3px"></span>' + x[1] + '</div>'; }).join(''); } });
  reg({ id: 'mx_q', grp: 'Samples and wells', label: 'Mexico RNMCA water-quality sites', tag: 'OBSERVED', ids: ['mxq-pts'], hi: ['mxq-pts'],
    load: function () { return U.layer('mx_quality_sites.json'); },
    build: function (g) {
      add({ mxq: { type: 'geojson', data: fc(g.sites.map(function (s) { return pt(s.lon, s.lat, s); })) } }, [circ('mxq-pts', 'mxq', 'mx_q', { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 1.8, 8, 5], 'circle-color': ['match', ['get', 'flag'], 'Verde', '#3ddc97', 'Azul', '#38c7ff', 'Amarillo', '#ffd37a', 'Rojo', '#ff5c6c', 'Morado', '#b06cff', '#7d8aa3'], 'circle-opacity': 0.8 })]);
    },
    legend: function () { return '<div class="lg-t">CONAGUA colour flag ' + U.lbl('OBSERVED') + '</div><div class="lg-grid">' + [['#3ddc97', 'Verde'], ['#38c7ff', 'Azul'], ['#ffd37a', 'Amarillo'], ['#ff5c6c', 'Rojo'], ['#b06cff', 'Morado']].map(function (x) { return '<div class="lg-row"><span class="lg-sw" style="background:' + x[0] + '"></span>' + x[1] + '</div>'; }).join('') + '</div>'; } });
  reg({ id: 'mx_piezo', grp: 'Samples and wells', label: 'Mexico piezometric network stations', tag: 'OBSERVED', ids: ['mxp-pts'], hi: ['mxp-pts'],
    load: function () { return U.layer('mx_piezo.json'); },
    build: function (g) { add({ mxp: { type: 'geojson', data: fc(g.rows.map(function (r) { return pt(r[0], r[1], {}); })) } }, [circ('mxp-pts', 'mxp', 'mx_piezo', { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 1.2, 8, 3.5], 'circle-color': '#9fb6d8', 'circle-opacity': 0.55 })]); },
    legend: function () { return '<div class="lg-row"><span class="lg-sw" style="background:#9fb6d8"></span>Piezometric station ' + U.lbl('OBSERVED') + '</div>'; } });
  reg({ id: 'ggmn', grp: 'Samples and wells', label: 'IGRAC GGMN global registry (1° cells)', tag: 'OBSERVED', ids: ['ggmn-c'], hi: ['ggmn-c'],
    load: function () { return U.layer('ggmn_global.json'); },
    build: function (g) {
      var f = g.cells.map(function (r) { return pt(r[1], r[0], { lat: r[0], lon: r[1], sites: r[2], lv: r[3], ql: r[4] }); });
      add({ gg: { type: 'geojson', data: fc(f) } }, [circ('ggmn-c', 'gg', 'ggmn', { 'circle-radius': ['interpolate', ['linear'], ['get', 'sites'], 1, 2.5, 100, 5, 1000, 9, 10000, 16], 'circle-color': ['case', ['>', ['get', 'ql'], 0], '#4cc39a', '#38c7ff'], 'circle-opacity': 0.6, 'circle-stroke-width': 0.4, 'circle-stroke-color': '#06101c' })]);
    },
    legend: function () { return '<div class="lg-t">GGMN registered points ' + U.lbl('OBSERVED') + '</div><div class="lg-row"><span class="lg-sw" style="background:#38c7ff"></span>Level series only</div><div class="lg-row"><span class="lg-sw" style="background:#4cc39a"></span>Includes quality series</div>'; } });
  reg({ id: 'npdes', grp: 'Wastewater', label: 'US major NPDES dischargers (POTW and industrial)', tag: 'OBSERVED', ids: ['npdes-pts'], hi: ['npdes-pts'],
    load: function () { return U.layer('npdes_majors.json'); },
    build: function (g) {
      var f = g.rows.map(function (r) { return pt(r[0], r[1], { name: r[2], id: r[3], st: r[4], county: r[5], potw: r[6], design: r[7], actual: r[8], status: r[9] }); });
      add({ np: { type: 'geojson', data: fc(f) } }, [circ('npdes-pts', 'np', 'npdes', { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 1.8, 8, 5], 'circle-color': ['case', ['==', ['get', 'potw'], 1], '#5b8def', '#ff9f43'], 'circle-opacity': 0.75 })]);
    },
    legend: function () { return '<div class="lg-t">NPDES majors ' + U.lbl('OBSERVED') + '</div><div class="lg-row"><span class="lg-sw" style="background:#5b8def"></span>Municipal (POTW)</div><div class="lg-row"><span class="lg-sw" style="background:#ff9f43"></span>Industrial</div>'; } });
  reg({ id: 'wser', grp: 'Wastewater', label: 'Canada WSER wastewater systems', tag: 'OBSERVED', ids: ['wser-pts'], hi: ['wser-pts'],
    load: function () { return U.layer('ca_wser.json'); },
    build: function (g) {
      var f = g.rows.map(function (r) { return pt(r[0], r[1], { system: r[2], owner: r[3], city: r[4], province: r[5], vol: r[6], kind: r[7], treat: r[8], status: r[9] }); });
      add({ ws: { type: 'geojson', data: fc(f) } }, [circ('wser-pts', 'ws', 'wser', { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 1.8, 8, 5], 'circle-color': '#2ec4b6', 'circle-opacity': 0.75 })]);
    },
    legend: function () { return '<div class="lg-row"><span class="lg-sw" style="background:#2ec4b6"></span>WSER system discharge point ' + U.lbl('OBSERVED') + '</div>'; } });
  reg({ id: 'dcs', grp: 'Data centers and siting', label: 'US data centers (FracTracker register)', tag: 'OBSERVED', ids: ['dcs-pts'], hi: ['dcs-pts'],
    load: function () { return U.layer('datacenters.json'); },
    build: function (g) {
      var f = g.rows.map(function (r) { return pt(r.lon, r.lat, { name: r.name, city: r.city, county: r.county, state: r.state, status: r.status, operator: r.operator, tenant: r.tenant, mw: r.mw_low ? (r.mw_high && r.mw_high !== r.mw_low ? U.n(r.mw_low) + ' to ' + U.n(r.mw_high) + ' MW' : U.n(r.mw_low) + ' MW') : null, cooling: [r.cooling_type, r.cooling_source].filter(Boolean).join(' / '), conf: r.loc_conf, updated: r.updated }); });
      var colr = ['match', ['get', 'status']]; Object.keys(DC_COL).forEach(function (k) { colr.push(k); colr.push(DC_COL[k]); }); colr.push('#7d8aa3');
      add({ dc: { type: 'geojson', data: fc(f) } }, [circ('dcs-pts', 'dc', 'dcs', { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 2.2, 9, 6], 'circle-color': colr, 'circle-opacity': 0.8, 'circle-stroke-width': 0.6, 'circle-stroke-color': '#06101c' })]);
    },
    legend: function () { return '<div class="lg-t">Data center status ' + U.lbl('OBSERVED') + '</div><div class="lg-grid">' + Object.keys(DC_COL).map(function (k) { return '<div class="lg-row"><span class="lg-sw" style="background:' + DC_COL[k] + '"></span>' + esc(k.split('/')[0]) + '</div>'; }).join('') + '</div>'; } });
  reg({ id: 'siting', grp: 'Data centers and siting', label: 'Texas siting score, default weights', tag: 'MODELED', ids: ['siting-c', 'lv-pt'], hi: ['siting-c', 'lv-pt'],
    load: function () { return U.layer('siting_tx.json'); },
    build: function (g) {
      var f = g.rows.map(function (r) { return pt(r[1], r[0], { lat: r[0], lon: r[1], score: r[2], sb: r[3], sp: r[4], ss: r[5], sd: r[6], bp: r[8], swd: r[11], dc: r[13], rank: r[17] }); });
      add({ st: { type: 'geojson', data: fc(f) }, lv: { type: 'geojson', data: fc([pt(g.longview.lon, g.longview.lat, { name: 'Longview' })]) } }, [
        circ('siting-c', 'st', 'siting', { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 4, 8, 14], 'circle-color': U.stepExpr('score', [30, 40, 50, 60], ['#16365e', '#1f6390', '#4cc39a', '#ffd37a', '#ff5c6c']), 'circle-opacity': 0.7 }),
        circ('lv-pt', 'lv', 'longview', { 'circle-radius': 8, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 2.6, 'circle-stroke-color': '#f2b84b' })]);
    },
    legend: function () { return U.legendSteps('Siting score (0 to 100)', [30, 40, 50, 60], ['#16365e', '#1f6390', '#4cc39a', '#ffd37a', '#ff5c6c'], String, 'MODELED') + '<div class="lg-row"><span class="lg-ring" style="background:none;border:2px solid #f2b84b"></span>Longview, TX</div>'; } });
})();
