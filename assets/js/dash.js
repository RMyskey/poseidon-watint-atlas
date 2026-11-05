/* Poseidon NARINT WATINT atlas: dashboards (supply flow, oil and gas, sample explorer, siting, chart builder). */
(function () {
  'use strict';
  var U = window.WTU, D = U.D, G = U.G, $ = U.$, $$ = U.$$, esc = U.esc, REF = D.ref, A = window.WTApp, H = A.H, LAYERS = A.LAYERS;
  function lay(id) { return LAYERS.filter(function (l) { return l.id === id; })[0]; }
  function pts(arr, f) { return arr.map(f); }

  /* ---------- generic dashboard map: registry layers on a secondary map, with popups ---------- */
  function dashMap(opts) {
    var map = U.mkMap({ id: opts.id, center: opts.center, zoom: opts.zoom, readout: opts.readout, sources: { sel: { type: 'geojson', data: U.fc() } }, layers: [{ id: 'sel-halo', type: 'circle', source: 'sel', paint: { 'circle-radius': 1, 'circle-opacity': 0 } }] });
    if (!map) return null;
    var state = {}, pop = new maplibregl.Popup({ maxWidth: '320px', offset: 10 });
    function setL(id, on) {
      var L = lay(id); state[id] = on;
      var cb = $('input[data-d="' + opts.id + ':' + id + '"]'); if (cb) cb.checked = on;
      if (on && !state['_l' + id]) {
        state['_l' + id] = 'loading';
        Promise.resolve(L.load()).then(function (d) { var m0 = A.map; A.map = map; try { L.build(d); } finally { A.map = m0; } state['_l' + id] = true; L.ids.forEach(function (i) { U.setVis(map, i, !!state[id]); }); legend(); })
          .catch(function (e) { state['_l' + id] = false; console.warn('dash layer', id, e); });
      } else if (state['_l' + id] === true) L.ids.forEach(function (i) { U.setVis(map, i, on); });
      legend();
    }
    function legend() {
      var el = opts.legend && $(opts.legend); if (!el) return;
      el.innerHTML = opts.layers.filter(function (id) { return state[id]; }).map(function (id) { var L = lay(id); return L.legend.call(L); }).join('<hr style="border:0;border-top:1px solid #1a2638;margin:6px 0">');
    }
    var box = $(opts.box);
    box.innerHTML = opts.layers.map(function (id) { var L = lay(id); return '<label class="lyr"><input type="checkbox" data-d="' + opts.id + ':' + id + '"' + (opts.on.indexOf(id) >= 0 ? ' checked' : '') + '><span>' + esc(L.label) + '</span></label>'; }).join('');
    $$('input', box).forEach(function (cb) { cb.onchange = function () { setL(cb.dataset.d.split(':')[1], cb.checked); }; });
    map.on('load', function () { opts.on.forEach(function (id) { setL(id, true); }); });
    map.on('click', function (e) {
      var ly = []; opts.layers.forEach(function (id) { if (state[id] && state['_l' + id] === true) lay(id).hi.forEach(function (i) { if (map.getLayer(i)) ly.push(i); }); });
      var r = ly.length ? map.queryRenderedFeatures([[e.point.x - 5, e.point.y - 5], [e.point.x + 5, e.point.y + 5]], { layers: ly }) : [];
      r.sort(function (a, b) { return (a.geometry.type === 'Point' ? 0 : 1) - (b.geometry.type === 'Point' ? 0 : 1); });
      if (!r.length) { pop.remove(); return; }
      var f = r[0], h = H[(f.layer.metadata || {}).wt]; if (!h) return;
      var t = h(f.properties), rows = (t.rows || []).filter(function (x) { return x; });
      var c = f.geometry.type === 'Point' ? f.geometry.coordinates : [e.lngLat.lng, e.lngLat.lat];
      pop.setLngLat(c).setHTML('<div class="pp-n">' + esc(t.title) + '</div><div class="small">' + esc(t.kick) + ' ' + (t.label ? U.lbl(t.label) : '') + '</div>' + (rows.length ? '<table class="kvt">' + rows.map(function (x) { return '<tr><td>' + esc(x[0]) + '</td><td>' + esc(x[1]) + '</td></tr>'; }).join('') + '</table>' : '') +
        '<div class="small" style="margin-top:4px">' + G.mgrs(c[1], c[0]) + ' · ' + (t.prec ? esc(t.prec + ' · ' + (REF.precision[t.prec] || {}).label) : '') + '</div><div class="small">' + esc(t.asof ? (/^\d{4}-\d\d-\d\dT/.test(t.asof) ? U.stamp(t.asof) : t.asof) : '') + '</div>').addTo(map);
    });
    map.on('mousemove', function (e) {
      var ly = []; opts.layers.forEach(function (id) { if (state[id] && state['_l' + id] === true) lay(id).hi.forEach(function (i) { if (map.getLayer(i)) ly.push(i); }); });
      map.getCanvas().style.cursor = ly.length && map.queryRenderedFeatures(e.point, { layers: ly }).length ? 'pointer' : '';
    });
    return { map: map, set: setL, state: state };
  }

  /* ---------- Supply flow ---------- */
  function sankeyOption(sk, colors, fmtv) {
    var names = {}; sk.links.forEach(function (l) { names[l.source] = 1; names[l.target] = 1; });
    var nodes = Object.keys(names).map(function (n) { return { name: n, itemStyle: { color: colors(n) } }; });
    return { tooltip: Object.assign({}, U.TIP, { formatter: function (p) { return p.dataType === 'edge' ? esc(p.data.source) + ' → ' + esc(p.data.target) + '<br><b>' + fmtv(p.data.value) + '</b>' : '<b>' + esc(p.name) + '</b><br>' + fmtv(p.value); } }),
      series: [{ type: 'sankey', data: nodes, links: sk.links, left: 8, right: 180, top: 10, bottom: 10, nodeGap: 12, nodeWidth: 14, emphasis: { focus: 'adjacency' }, lineStyle: { color: 'gradient', opacity: 0.4, curveness: 0.5 }, label: { color: '#e9eff8', fontSize: 11, width: 170, overflow: 'break', formatter: function (p) { return p.name.replace(/^(Source|Size|ECHO flag): /, ''); } } }] };
  }
  function initFlow() {
    var F = D.flow, a = F.sankeyA, b = F.sankeyB;
    $('#skATitle').innerHTML = esc(a.title) + ' ' + U.lbl('OBSERVED');
    $('#skANote').innerHTML = esc('As of ' + U.stamp(a.asof) + '. ' + U.n(a.systems) + ' community water systems serving ' + U.n(a.population) + ' people. ' + a.note) + ' Source: ' + U.srcLink('echo_sdwa') + '.';
    $('#skBTitle').innerHTML = esc(b.title) + ' ' + U.lbl('ANALYTIC ASSESSMENT');
    $('#skBNote').innerHTML = esc(b.note) + ' Source: ' + U.srcLink('ttu_leeds') + ' (' + esc(b.asof) + ').';
    var colA = function (n) { return /Groundwater/.test(n) ? '#2397a8' : /Surface/.test(n) ? '#5b8def' : /Health-based/.test(n) ? '#ff5c6c' : /No health/.test(n) ? '#3ddc97' : '#7d8aa3'; };
    var colB = function (n) { return /Recycled/.test(n) ? '#3ddc97' : /Remainder/.test(n) ? '#ffb547' : '#38c7ff'; };
    U.whenVisible($('#sankeyA'), function () {
      U.chart('sankeyA').setOption(sankeyOption(a, colA, function (v) { return U.n(v) + ' people'; }));
      U.chart('sankeyB').setOption(sankeyOption(b, colB, function (v) { return v + ' million bbl/day'; }));
    });
    // chain
    $('#chain').innerHTML = F.chain.stages.map(function (s) {
      return '<div class="stage"><h4>' + esc(s.name) + '</h4>' + s.items.map(function (i) { return '<div class="it"><a data-layer="' + esc(i.layer) + '" title="Source: ' + esc((D.sources[i.src] || {}).name || i.src) + '">' + esc(i.label) + '</a><b>' + U.n(i.n) + '</b></div>'; }).join('') + '</div>';
    }).join('');
    $('#chain').insertAdjacentHTML('afterend', '<p class="small">' + U.lbl('ANALYTIC ASSESSMENT') + ' Stage assignment is the atlas\'s; counts are OBSERVED from each source (see Data register for as-of dates). Stages with no open data (for example US treatment-plant capacity) are not shown rather than estimated. Click an item to show its layer on the map.</p>');
    var map2layer = { sdwa_county: 'sdwa', ca_wser: 'wser', ca_dwa: 'ca_dwa', npdes_majors: 'npdes', datacenters: 'dcs', tx_swd: 'swd', nbga_grid: 'nbga', mx_aquifers: 'mx_aq', pwdb_grid: 'pwdb', mx_plants: null };
    $$('#chain a[data-layer]').forEach(function (el) { el.onclick = function () { var id = map2layer[el.dataset.layer]; if (!id) { U.toast('State-level counts only; no map layer'); return; } A.setLayer(id, true); document.getElementById('map').scrollIntoView(); }; });
    // produced water table
    var pw = F.produced_water, c = F.calc;
    var rows = pw.inputs.map(function (x) { return '<tr><td>' + esc(x.label) + '</td><td class="num">' + U.n(x.bpd) + '</td><td class="num">' + U.n(x.mgal_per_day, 1) + '</td><td class="num">' + U.n(x.pools_per_day) + '</td><td>' + U.srcLink(x.src) + '</td></tr>'; });
    rows.push('<tr><td>Claim to test: 8 billion gallons per day (Anthropocene Magazine article and reel)</td><td class="num">' + U.n(c.claim_8bgd_bbl_per_day) + '</td><td class="num">8,000.0</td><td class="num">' + U.n(c.claim_8bgd_pools) + '</td><td>' + U.srcLink('anthropocene') + '</td></tr>');
    rows.push('<tr><td>One large data center at the upper figure of 5 million gallons per day</td><td class="num">' + U.n(c.dc_max_bbl_per_day) + '</td><td class="num">5.0</td><td class="num">' + U.n(5e6 / (2500000 / 3.785411784)) + '</td><td>' + U.srcLink('eesi') + '</td></tr>');
    $('#pwTable').innerHTML = '<thead><tr><th>Quantity (source figure)</th><th>barrels/day</th><th>million gal/day</th><th>Olympic pools/day</th><th>Source</th></tr></thead><tbody>' + rows.join('') + '</tbody>';
    $('#pwNote').innerHTML = esc(pw.conversion + '. The 8 billion figure is about ' + c.ratio_claim_to_ttu + ' times the Texas Tech figure. Permian output of 20 million bbl/day equals about ' + c.dc_equiv_per_permian + ' data centers at 5 million gal/day, before any treatment, salinity or logistics constraints. Of the Permian figure, about 5.5 million bbl/day is recycled inside oil and gas operations (Texas Tech), leaving about 14.5 million (ANALYTIC: 20 minus 5.5, about ' + U.n(c.net_after_recycling_mgal) + ' million gal/day).');
    initLogistics();
  }
  function initLogistics() {
    U.layer('logistics_tx.json').then(function (g) {
      var rows = g.rows, sortK = 'cell_rank', asc = true, q = '', st = '';
      var stats = {}; rows.forEach(function (r) { stats[r.status] = 1; });
      $('#lgStatus').innerHTML = '<option value="">All statuses</option>' + Object.keys(stats).map(function (s) { return '<option>' + esc(s) + '</option>'; }).join('');
      var cols = [['name', 'Data center'], ['county', 'County'], ['status', 'Status'], ['operator', 'Operator'], ['mw_high', 'MW'], ['swd_25km', 'Wells ≤25 km'], ['swd_50km', 'Wells ≤50 km'], ['nearest_commercial_disposal_km', 'Nearest comm. disposal (km)'], ['nearest_potw_major_km', 'Nearest major POTW (km)'], ['cell_score', 'Siting score'], ['cell_rank', 'Rank']];
      function view() { return rows.filter(function (r) { return (!st || r.status === st) && (!q || (r.name + r.county + r.operator + r.city).toLowerCase().indexOf(q) >= 0); }); }
      function render() {
        var v = view().slice().sort(function (a, b) { var x = a[sortK], y = b[sortK]; if (x === y) return 0; if (x === null || x === undefined || x === '') return 1; if (y === null || y === undefined || y === '') return -1; return (x > y ? 1 : -1) * (asc ? 1 : -1); });
        $('#lgCount').textContent = v.length + ' of ' + rows.length + ' Texas records';
        $('#lgTable').innerHTML = '<thead><tr>' + cols.map(function (c) { return '<th data-k="' + c[0] + '">' + c[1] + '</th>'; }).join('') + '</tr></thead><tbody>' + v.slice(0, 200).map(function (r) {
          return '<tr>' + cols.map(function (c) { var x = r[c[0]]; return '<td' + (typeof x === 'number' ? ' class="num"' : '') + '>' + esc(typeof x === 'number' ? U.n(x, c[0].indexOf('km') >= 0 || c[0] === 'cell_score' ? 1 : 0) : (x || '')) + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody>';
        $$('#lgTable th').forEach(function (th) { th.style.cursor = 'pointer'; th.onclick = function () { if (sortK === th.dataset.k) asc = !asc; else { sortK = th.dataset.k; asc = true; } render(); }; });
      }
      $('#lgSearch').oninput = function () { q = this.value.toLowerCase(); render(); };
      $('#lgStatus').onchange = function () { st = this.value; render(); };
      $('#lgCsv').onclick = function () { U.download('poseidon_tx_datacenter_logistics.csv', U.toCSV(view(), Object.keys(rows[0])), 'text/csv'); };
      render();
    }).catch(function () { $('#lgTable').innerHTML = '<tbody><tr><td>Logistics layer not available.</td></tr></tbody>'; });
  }

  /* ---------- Oil and gas ---------- */
  function initOilGas() {
    var el = $('#ogMap');
    U.whenVisible(el, function () {
      var dm = dashMap({ id: 'ogMap', center: [-102.3, 31.8], zoom: 6.2, readout: '#ogReadout', box: '#ogLayers', legend: '#ogLegend', layers: ['wells', 'swd', 'swd_vol', 'quakes_na', 'pwdb', 'nbga'], on: ['wells', 'swd', 'quakes_na'] });
      if (!dm) return;
      $$('#ogPreset button').forEach(function (b) { b.onclick = function () { $$('#ogPreset button').forEach(function (x) { x.classList.toggle('on', x === b); }); var r = REF.regions[b.dataset.r]; dm.map.flyTo({ center: r.center, zoom: r.zoom, duration: 1000 }); }; });
      window.__ogmap = dm.map;
    });
    var OGF = [['tx', 'Texas'], ['nm', 'New Mexico'], ['ok', 'Oklahoma'], ['ab', 'Alberta'], ['bc', 'British Columbia'], ['sk', 'Saskatchewan']];
    Promise.all([U.layer('og_na_summary.json'), U.layer('quakes.json')].concat(OGF.map(function (o) { return U.layer(o[0] + '_wells_grid.json').catch(function () { return null; }); }))).then(function (d) {
      var sm = d[0], grids = d.slice(2), names = [['producing', 'Producing', '#3ddc97'], ['shut_in', 'Shut-in', '#ffb547'], ['plugged', 'Plugged / abandoned', '#7d8aa3'], ['injection_disposal', 'Injection / disposal', '#38c7ff'], ['other', 'Other / unclassified', '#5b6a85']];
      var J = sm.jurisdictions.slice().sort(function (a, b) { return a.records - b.records; });
      U.whenVisible($('#ogBars'), function () {
        U.chart('ogBars').setOption({ tooltip: Object.assign({}, U.TIP, { trigger: 'axis', axisPointer: { type: 'shadow' } }), legend: { data: names.map(function (n) { return n[1]; }), textStyle: { color: '#a3b2c8', fontSize: 10 }, top: 0, itemWidth: 10, itemHeight: 8 }, grid: { left: 100, right: 40, top: 40, bottom: 24 }, xAxis: Object.assign({ type: 'value' }, U.AX), yAxis: Object.assign({ type: 'category', data: J.map(function (x) { return x.name; }) }, U.AX),
          series: names.map(function (n) { return { name: n[1], type: 'bar', stack: 'c', data: J.map(function (x) { return x.by_class[n[0]]; }), itemStyle: { color: n[2] } }; }) });
      });
      $('#ogBarsNote').innerHTML = esc('Total ' + U.n(J.reduce(function (t, x) { return t + x.records; }, 0)) + ' records. Class grouping is the atlas\'s mapping of each regulator\'s status codes. Sources: ') + J.slice().reverse().map(function (x) { return U.srcLink(x.src); }).join(', ') + esc('; as of ' + U.stamp(sm.asof) + '. ') + U.lbl('OBSERVED');
      // top disposal cells, all jurisdictions
      var all = []; grids.forEach(function (g, i) { if (g) g.rows.forEach(function (r) { all.push([r, OGF[i][1]]); }); });
      var top = all.sort(function (a, b) { return b[0][5] - a[0][5]; }).slice(0, 12);
      $('#ogTop').innerHTML = '<thead><tr><th>Cell centre</th><th>Region</th><th>MGRS</th><th>Inj./disposal</th><th>Producing</th></tr></thead><tbody>' + top.map(function (x) { var r = x[0]; return '<tr><td>' + r[0].toFixed(2) + ', ' + r[1].toFixed(2) + '</td><td>' + esc(x[1]) + '</td><td class="mono">' + G.mgrs(r[0], r[1]).slice(0, 9) + '…</td><td class="num">' + U.n(r[5]) + '</td><td class="num">' + U.n(r[2]) + '</td></tr>'; }).join('') + '</tbody>';
      // volumes (NM, OK)
      var tv = sm.top_volume_wells.slice(0, 15), vj = sm.jurisdictions.filter(function (x) { return x.volume; });
      U.whenVisible($('#ogVol'), function () {
        U.chart('ogVol').setOption({ tooltip: Object.assign({}, U.TIP, { formatter: function (p) { var w = tv[tv.length - 1 - p.dataIndex]; return esc(w.jur + ' ' + w.subtype) + '<br>' + w.lat.toFixed(3) + ', ' + w.lon.toFixed(3) + '<br>' + U.n(w.vol) + ' bbl (unit read as barrels)'; } }), grid: { left: 150, right: 30, top: 8, bottom: 26 },
          xAxis: Object.assign({ type: 'value', name: 'million bbl', nameLocation: 'middle', nameGap: 20 }, U.AX), yAxis: Object.assign({ type: 'category', data: tv.map(function (w) { return w.jur + ' ' + w.lat.toFixed(2) + ', ' + w.lon.toFixed(2); }).reverse() }, U.AX),
          series: [{ type: 'bar', data: tv.map(function (w) { return { value: +(w.vol / 1e6).toFixed(2), itemStyle: { color: w.jur === 'NM' ? '#ffb547' : '#b06cff' } }; }).reverse() }] });
      });
      $('#ogVolNote').innerHTML = esc('Top 15 wells by reported injection volume: New Mexico (OCD, rolling 12 months) and Oklahoma (OCC, calendar 2025). ') + vj.map(function (x) { return esc(x.name + ' total ' + U.n(x.volume.total) + ' bbl (' + x.volume.kind + ', ' + U.n(x.volume.wells) + ' wells; saltwater disposal alone ' + U.n(x.volume.swd_only_total) + ' bbl)'); }).join('; ') + esc('. The services do not state a unit; it is read as barrels (' + vj.map(function (x) { return x.name + ' about ' + (x.volume.total / 365e6).toFixed(1) + ' million bbl/day'; }).join(', ') + ' if so, plausible against the Permian figure of about 20 million bbl/day from Texas Tech/TAWC). Not regulator-confirmed. ') + U.srcLink('nm_ocd') + ', ' + U.srcLink('ok_occ');
      $('#ogJur').innerHTML = '<thead><tr><th>Region</th><th>Inj./disp. wells</th><th>Per-well volume</th><th>As of</th></tr></thead><tbody>' + sm.jurisdictions.map(function (x) { return '<tr><td>' + esc(x.name) + '</td><td class="num">' + U.n(x.injection_disposal_points) + '</td><td>' + (x.volume ? esc(x.volume.kind) : 'not published in layer') + '</td><td>' + esc(U.date(x.asof)) + '</td></tr>'; }).join('') + '</tbody>';
      // quakes box
      var q = d[1], cells = q.na_grid.filter(function (r) { return r[0] >= 30 && r[0] <= 33.5 && r[1] >= -105 && r[1] <= -100; });
      var tot = cells.reduce(function (s, r) { return s + r[2]; }, 0), mx = Math.max.apply(null, cells.map(function (r) { return r[3]; }));
      var topq = cells.slice().sort(function (a, b) { return b[2] - a[2]; }).slice(0, 10);
      U.whenVisible($('#ogQuake'), function () {
        U.chart('ogQuake').setOption({ tooltip: Object.assign({}, U.TIP, { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: function (p) { var r = topq[p[0].dataIndex]; return 'Cell ' + r[0] + ', ' + r[1] + '<br>' + r[2] + ' events, largest M' + r[3]; } }), grid: { left: 50, right: 20, top: 10, bottom: 54 },
          xAxis: Object.assign({ type: 'category', data: topq.map(function (r) { return r[0].toFixed(1) + ', ' + r[1].toFixed(1); }), axisLabel: { color: '#a3b2c8', rotate: 40, fontSize: 10 } }, {}), yAxis: Object.assign({ type: 'value', name: 'M2.5+ events' }, U.AX),
          series: [{ type: 'bar', data: topq.map(function (r) { return { value: r[2], itemStyle: { color: r[3] >= 4.5 ? '#ff5c6c' : r[3] >= 4 ? '#ff9f43' : '#ffd37a' } }; }) }] });
      });
      $('#ogQuakeNote').innerHTML = esc(U.n(tot) + ' M2.5+ events in 30.0 to 33.5 N, 105.0 to 100.0 W, ' + q.na_window.from + ' to ' + q.na_window.to + ', largest M' + mx + '. Top 10 of ' + cells.length + ' half-degree cells; colour = largest magnitude in the cell. USGS does not label events natural or induced.') + ' ' + U.srcLink('usgs_quakes');
    }).catch(function (e) { console.warn(e); });
    var P = D.pwdb_basins.slice().sort(function (a, b) { return b.tds_median_mgL - a.tds_median_mgL; }).filter(function (b) { return b.n_tds >= 100; }).slice(0, 14);
    U.whenVisible($('#ogTds'), function () {
      var names = P.map(function (b) { return b.basin; }).reverse();
      U.chart('ogTds').setOption({ tooltip: Object.assign({}, U.TIP, { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: function (p) { var b = P[P.length - 1 - p[0].dataIndex]; return '<b>' + esc(b.basin) + '</b><br>Median ' + U.n(b.tds_median_mgL) + ' mg/L<br>P10 to P90: ' + U.n(b.tds_p10_mgL) + ' to ' + U.n(b.tds_p90_mgL) + '<br>' + U.n(b.n_tds) + ' samples'; } }),
        grid: { left: 130, right: 20, top: 14, bottom: 26 }, xAxis: Object.assign({ type: 'log', min: 100 }, U.AX), yAxis: Object.assign({ type: 'category', data: names }, U.AX),
        series: [{ type: 'bar', data: P.map(function (b) { return b.tds_median_mgL; }).reverse(), itemStyle: { color: '#5b8def' }, markLine: { silent: true, symbol: 'none', lineStyle: { color: '#3ddc97', type: 'dashed' }, label: { color: '#3ddc97', formatter: 'EPA SMCL 500' }, data: [{ xAxis: 500 }] } },
          { type: 'scatter', symbol: 'rect', symbolSize: [3, 14], itemStyle: { color: '#ffd37a' }, data: P.map(function (b, i) { return [b.tds_p10_mgL, P.length - 1 - i]; }).map(function (x) { return [x[0], x[1]]; }) },
          { type: 'scatter', symbol: 'rect', symbolSize: [3, 14], itemStyle: { color: '#ff9f43' }, data: P.map(function (b, i) { return [b.tds_p90_mgL, P.length - 1 - i]; }) }] });
    });
  }

  /* ---------- Sample explorer ---------- */
  var SX = { param: 'nitrate', basis: 'epa', agg: 'county', stat: 'median', map: null, ready: false, cty: null, huc: null, top: null, wq: null, mx: null, stateOf: null };
  var RATIO_B = [0.25, 0.5, 1, 2, 4], RATIO_C = ['#1a2d46', '#2a6f9a', '#4cc39a', '#ffd37a', '#ff9f43', '#ff5c6c'];
  function limOf() { var l = U.limit(SX.param, SX.basis); return l ? l.value : null; }
  function sxLimitNote() {
    var L = U.limit(SX.param, SX.basis), p = REF.limits.parameters[SX.param];
    $('#sxLimitNote').innerHTML = (L && L.value !== null ? '<b>' + esc(L.value + ' ' + p.unit) + '</b> · ' : '<b>No single-value limit</b> · ') + esc(L ? L.type : '') + (L && L.url ? ' · <a href="' + esc(L.url) + '" target="_blank" rel="noopener">source</a>' : '') + ' ' + U.lbl('CURATED');
  }
  function sxColorExpr(prop, lim) { return lim ? U.stepExpr(prop, RATIO_B, RATIO_C) : U.stepExpr(prop, [1, 10, 100, 1000], ['#1a2d46', '#2a6f9a', '#4cc39a', '#ffd37a', '#ff9f43']); }
  var STATCOL = { median: 2, p90: 3, max: 4, pct: 5 };
  function sxValue(rec, stat) { return rec[STATCOL[stat]]; }
  function sxRefresh() {
    if (!SX.ready || !SX.cty) return;
    var map = SX.map, lim = limOf(), param = SX.param, stat = SX.stat, pU = REF.limits.parameters[param].unit;
    var pctMode = stat === 'pct';
    var useLim = pctMode ? U.limit(param, 'epa').value : lim;
    var cdata = SX.wq.data[param] || {}, fl = U.fc(), cent = U.fc();
    // counties
    var g = SX.cty;
    g.features.forEach(function (f) {
      var r = cdata[f.properties.fips], p = f.properties;
      if (r) { var v = sxValue(r, stat); p.val = v; p.n = r[0]; p.sites = r[1]; p.med = r[2]; p.p90 = r[3]; p.max = r[4]; p.pct = r[5]; p.yr = r[6]; p.ratio = pctMode ? v : (lim ? v / lim : v); } else { p.val = null; p.ratio = null; p.n = 0; }
    });
    var src = map.getSource('sx-cty'); if (src) src.setData(g);
    var pb = pctMode ? [1, 5, 10, 25, 50] : null;
    if (map.getLayer('sx-fill')) {
      var expr = pctMode ? ['case', ['==', ['get', 'ratio'], null], 'rgba(0,0,0,0)', U.stepExpr('ratio', pb, RATIO_C)] : ['case', ['==', ['get', 'ratio'], null], 'rgba(0,0,0,0)', sxColorExpr('ratio', lim)];
      map.setPaintProperty('sx-fill', 'fill-color', expr);
      U.setVis(map, 'sx-fill', SX.agg === 'county'); U.setVis(map, 'sx-huc', SX.agg === 'huc8');
    }
    // huc8
    var hrows = (SX.huc.data[param] || []).map(function (r) { var v = sxValue(r.slice(3), stat); return U.pt(r[2], r[1], { huc8: r[0], n: r[3], sites: r[4], med: r[5], p90: r[6], max: r[7], pct: r[8], yr: r[9], val: v, ratio: pctMode ? v : (lim ? v / lim : v) }); });
    var hs = map.getSource('sx-huc'); if (hs) hs.setData(U.fc(hrows));
    if (map.getLayer('sx-huc')) map.setPaintProperty('sx-huc', 'circle-color', pctMode ? U.stepExpr('ratio', pb, RATIO_C) : sxColorExpr('ratio', lim));
    // mexico
    var mxs = [];
    if ($('#sxMx').checked && SX.mx) {
      var key = { tds: 'tds', nitrate: 'no3n', arsenic: 'as_mgL' }[param];
      SX.mx.sites.forEach(function (s) {
        if (s.t !== 'gw') return;
        var v = key ? s[key] : null; if (key === 'as_mgL' && v !== null && v !== undefined && v !== '') v = v * 1000;
        var nl = REF.limits.parameters[param].nom127.value, cat = (v === null || v === undefined || v === '' || nl === null) ? 'na' : (v > nl ? 'over' : 'ok');
        mxs.push(U.pt(s.lon, s.lat, { n: s.n, st: s.st, mun: s.mun, v: v === '' ? null : v, cat: cat, flag: s.flag, yr: s.yr, t: 'gw', aq: s.aq, tds: s.tds, no3n: s.no3n, as_mgL: s.as_mgL }));
      });
    }
    var ms = map.getSource('sx-mx'); if (ms) ms.setData(U.fc(mxs));
    // legend
    var cols = RATIO_C, h = '';
    if (pctMode) h = U.legendSteps('% of results above EPA value', pb, cols, String, 'OBSERVED');
    else if (lim) h = U.legendSteps(({ median: 'Median', p90: '90th pct', max: 'Maximum' })[stat] + ' ÷ limit (' + lim + ' ' + pU + ')', RATIO_B, cols, function (v) { return v + '×'; }, 'ANALYTIC ASSESSMENT');
    else h = U.legendSteps('Value (' + pU + ') - no single limit', [1, 10, 100, 1000], ['#1a2d46', '#2a6f9a', '#4cc39a', '#ffd37a', '#ff9f43'], String, 'OBSERVED');
    h += '<div class="lg-row"><span class="lg-sw" style="background:#38c7ff;border-radius:50%;border:1px solid #fff"></span>Mexico RNMCA wells: ' + (REF.limits.parameters[param].nom127.value !== null && ['tds', 'nitrate', 'arsenic'].indexOf(param) >= 0 ? '<span style="color:#ff5c6c">above</span> / <span style="color:#3ddc97">below</span> NOM-127' : 'no NOM-127 value for this parameter') + '</div>';
    $('#sxLegend').innerHTML = h;
    if (pctMode && SX.basis !== 'epa') $('#sxNote').innerHTML = '% above limit is precomputed against the EPA value only. ' + U.srcLink('wqp');
    // state bars: counties with statistic above limit
    var byS = {}, lm = useLim;
    Object.keys(cdata).forEach(function (fips) { var s = SX.stateOf[fips.slice(0, 2)]; if (!s) return; var v = sxValue(cdata[fips], pctMode ? 'median' : stat); var o = byS[s] || (byS[s] = { n: 0, over: 0 }); o.n++; if (lm !== null && lm !== undefined && v > lm) o.over++; });
    var arr = Object.keys(byS).map(function (s) { return { s: s, n: byS[s].n, over: byS[s].over, share: 100 * byS[s].over / byS[s].n }; }).filter(function (x) { return x.n >= 5; }).sort(function (a, b) { return b.share - a.share; }).slice(0, 14);
    $('#sxTitle').innerHTML = 'States with the highest share of counties above the limit ' + U.lbl('ANALYTIC ASSESSMENT');
    var ch = U.chart('sxBars');
    if (ch) { ch.setOption({ tooltip: Object.assign({}, U.TIP, { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: function (p) { var x = arr[arr.length - 1 - p[0].dataIndex]; return x.s + ': ' + x.over + ' of ' + x.n + ' counties (' + x.share.toFixed(0) + '%)'; } }), grid: { left: 40, right: 24, top: 10, bottom: 24 }, xAxis: Object.assign({ type: 'value', max: 100, name: '% of counties' }, U.AX), yAxis: Object.assign({ type: 'category', data: arr.map(function (x) { return x.s; }).reverse() }, U.AX), series: [{ type: 'bar', data: arr.map(function (x) { return x.share; }).reverse(), itemStyle: { color: '#ff9f43' } }] }, true); }
    $('#sxNote').innerHTML = (SX.basis !== 'epa' && pctMode ? '% above limit is precomputed against the EPA value only. ' : '') + esc('Counties with at least 5 monitored counties of data per state are ranked; "above" means the county ' + (pctMode ? 'median' : { median: 'median', p90: '90th percentile', max: 'maximum' }[stat]) + ' exceeds ' + (lm !== null && lm !== undefined ? lm + ' ' + pU : 'the limit (none defined)') + '. ') + U.srcLink('wqp') + ' · as of ' + esc(U.stamp(SX.wq.asof));
    // top sites
    var tops = (SX.top.data[param] || []).slice(0, 40);
    $('#sxTop').innerHTML = '<thead><tr><th>Max (' + esc(pU) + ')</th><th>×limit</th><th>State</th><th>MGRS</th><th>n</th></tr></thead><tbody>' + tops.map(function (r, i) { return '<tr data-i="' + i + '" style="cursor:pointer"><td class="num">' + U.sig(r[0]) + '</td><td class="num">' + (lim ? U.n(r[0] / lim, 1) + '×' : 'n/a') + '</td><td>' + esc(r[4]) + '</td><td class="mono">' + esc(G.mgrs(r[2], r[3]).slice(0, 12)) + '</td><td class="num">' + r[5] + '</td></tr>'; }).join('') + '</tbody>';
    $$('#sxTop tr[data-i]').forEach(function (tr) { tr.onclick = function () { var r = tops[+tr.dataset.i]; map.flyTo({ center: [r[3], r[2]], zoom: 9, duration: 900 }); }; });
    var mk = map.getSource('sx-top'); if (mk) mk.setData(U.fc(tops.slice(0, 40).map(function (r) { return U.pt(r[3], r[2], { v: r[0], st: r[4], n: r[5], yr: r[6], sid: r[1] }); })));
  }
  function initSamples() {
    var P = REF.limits.parameters;
    $('#sxParam').innerHTML = Object.keys(P).map(function (k) { return '<option value="' + k + '">' + esc(P[k].label + ' (' + P[k].unit + ')') + '</option>'; }).join('');
    $('#sxParam').value = SX.param;
    $('#sxLimit').innerHTML = '<option value="epa">EPA (US)</option><option value="health_canada">Health Canada</option><option value="nom127">NOM-127 (Mexico)</option>';
    sxLimitNote();
    ['sxParam', 'sxLimit', 'sxAgg', 'sxStat'].forEach(function (id) { $('#' + id).onchange = function () { SX.param = $('#sxParam').value; SX.basis = $('#sxLimit').value; SX.agg = $('#sxAgg').value; SX.stat = $('#sxStat').value; sxLimitNote(); sxRefresh(); }; });
    $('#sxMx').onchange = sxRefresh;
    // global register doc
    var gg = null;
    Promise.all([U.layer('ggmn_global.json'), U.layer('wqp_county.json')]).then(function (rr) {
      var g = rr[0], wqs = (rr[1] && rr[1].summary) || {};
      gg = g; var m = g.meta;
      var ctry = Object.keys(g.countries).map(function (k) { return [k, g.countries[k]]; }).sort(function (a, b) { return b[1].sites - a[1].sites; }), top = ctry.slice(0, 15);
      $('#globalDoc').innerHTML = '<ul class="bul"><li><b>IGRAC GGMN</b>: ' + U.n(m.records) + ' registered monitoring points from ' + ctry.length + ' countries via the public GGIS WFS (as of ' + esc(m.asof) + '). It is a registry of points contributed by national agencies; the open feed carries counts of level and quality records, not chemistry values. ' + U.srcLink('igrac') + '</li>' +
        '<li><b>UNEP GEMStat</b>: global freshwater quality; no public API; the data portal limits a request to 675 stations and larger requests are by custom request. Not ingested. ' + U.srcLink('gemstat') + '</li>' +
        '<li><b>US Water Quality Portal</b>: ' + U.n(Object.keys(wqs).reduce(function (s, k) { return Math.max(s, wqs[k].sites); }, 0)) + ' monitoring sites for the most-sampled parameter (TDS, chloride, nitrate, arsenic, PFAS) since 2010; submitted by USGS, EPA, states and other agencies. Open, with chemistry. ' + U.srcLink('wqp') + '</li>' +
        '<li><b>CONAGUA RNMCA</b> (Mexico) and <b>ISC / ECCC</b> (Canada) publish national files with their own definitions; the atlas shows them separately and does not merge them with GGMN.</li>' +
        '<li><b>Why there is no complete global dataset:</b> national networks use different well definitions, depths, parameters and sampling frequencies; many countries do not publish open data; several programs restrict bulk access; and registries (GGMN) hold locations and metadata far more often than chemistry. Treat any global count as a floor.</li></ul>';
      U.whenVisible($('#ggChart'), function () {
        var t = top.slice().reverse();
        U.chart('ggChart').setOption({ tooltip: Object.assign({}, U.TIP, { trigger: 'axis', axisPointer: { type: 'shadow' } }), legend: { data: ['With level series', 'With quality series'], textStyle: { color: '#a3b2c8' }, top: 0 }, grid: { left: 110, right: 20, top: 30, bottom: 24 }, xAxis: Object.assign({ type: 'log', min: 1 }, U.AX), yAxis: Object.assign({ type: 'category', data: t.map(function (x) { return x[0]; }) }, U.AX),
          series: [{ name: 'With level series', type: 'bar', data: t.map(function (x) { return x[1].level || null; }), itemStyle: { color: '#38c7ff' } }, { name: 'With quality series', type: 'bar', data: t.map(function (x) { return x[1].quality || null; }), itemStyle: { color: '#4cc39a' } }] });
      });
      $('#ggNote').innerHTML = esc('Registered points per country, log scale. Countries absent from the registry are not necessarily unmonitored. As of ' + m.asof + '. ') + U.lbl('OBSERVED');
    }).catch(function () { $('#globalDoc').textContent = 'GGMN layer not available.'; });
    U.whenVisible($('#sxMap'), function () {
      Promise.all([U.layer('us_counties.geojson'), U.layer('wqp_county.json'), U.layer('wqp_huc8.json'), U.layer('wqp_top_sites.json'), U.layer('mx_quality_sites.json')]).then(function (d) {
        SX.cty = JSON.parse(JSON.stringify(d[0])); SX.wq = d[1]; SX.huc = d[2]; SX.top = d[3]; SX.mx = d[4];
        SX.stateOf = {}; SX.cty.features.forEach(function (f) { SX.stateOf[f.properties.fips.slice(0, 2)] = f.properties.state; });
        var map = U.mkMap({ id: 'sxMap', center: [-98, 38.5], zoom: 3.4, readout: '#sxReadout', sources: { sel: { type: 'geojson', data: U.fc() }, 'sx-cty': { type: 'geojson', data: U.fc() }, 'sx-huc': { type: 'geojson', data: U.fc() }, 'sx-mx': { type: 'geojson', data: U.fc() }, 'sx-top': { type: 'geojson', data: U.fc() } },
          layers: [{ id: 'sel-halo', type: 'circle', source: 'sel', paint: { 'circle-radius': 1, 'circle-opacity': 0 } },
            { id: 'sx-fill', type: 'fill', source: 'sx-cty', paint: { 'fill-color': 'rgba(0,0,0,0)', 'fill-opacity': 0.7, 'fill-outline-color': 'rgba(120,150,190,.25)' }, metadata: { wt: 'sx' } },
            { id: 'sx-huc', type: 'circle', source: 'sx-huc', layout: { visibility: 'none' }, paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 3, 8, 9], 'circle-color': '#4cc39a', 'circle-opacity': 0.8, 'circle-stroke-width': 0.5, 'circle-stroke-color': '#06101c' }, metadata: { wt: 'sx' } },
            { id: 'sx-top', type: 'circle', source: 'sx-top', paint: { 'circle-radius': 4, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 1.4, 'circle-stroke-color': '#ffffff' }, metadata: { wt: 'sx' } },
            { id: 'sx-mx', type: 'circle', source: 'sx-mx', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 2, 8, 5], 'circle-color': ['match', ['get', 'cat'], 'over', '#ff5c6c', 'ok', '#3ddc97', '#7d8aa3'], 'circle-opacity': 0.85, 'circle-stroke-width': 0.4, 'circle-stroke-color': '#06101c' }, metadata: { wt: 'mx_q' } }] });
        SX.map = map;
        map.on('load', function () {
          SX.ready = true; sxRefresh();
          var pop = new maplibregl.Popup({ maxWidth: '300px', offset: 8 });
          map.on('click', function (e) {
            var r = map.queryRenderedFeatures([[e.point.x - 4, e.point.y - 4], [e.point.x + 4, e.point.y + 4]], { layers: ['sx-mx', 'sx-top', 'sx-huc', 'sx-fill'].filter(function (l) { return map.getLayoutProperty(l, 'visibility') !== 'none'; }) });
            if (!r.length) { pop.remove(); return; }
            var f = r[0], p = f.properties, pU = REF.limits.parameters[SX.param].unit, html = '';
            if (f.layer.id === 'sx-mx') { var t = H.mx_q(p); html = '<div class="pp-n">' + esc(t.title) + '</div><table class="kvt">' + t.rows.filter(function (x) { return x; }).map(function (x) { return '<tr><td>' + esc(x[0]) + '</td><td>' + esc(x[1]) + '</td></tr>'; }).join('') + '</table><div class="small">CONAGUA RNMCA · ' + U.lbl('OBSERVED') + '</div>'; }
            else if (f.layer.id === 'sx-top') html = '<div class="pp-n">Highest-result site ' + esc(p.sid) + '</div><div class="small">' + esc(p.st) + ' · max ' + U.sig(p.v) + ' ' + esc(pU) + ' · ' + p.n + ' results · latest ' + esc(p.yr) + '</div><div class="small">WQP · ' + U.lbl('OBSERVED') + '</div>';
            else { var nm = f.layer.id === 'sx-fill' ? esc(p.name) + ', ' + esc(p.state) : 'HUC8 ' + esc(p.huc8); html = '<div class="pp-n">' + nm + '</div><table class="kvt"><tr><td>Results / sites</td><td>' + U.n(p.n) + ' / ' + U.n(p.sites) + '</td></tr><tr><td>Median</td><td>' + U.sig(p.med) + ' ' + esc(pU) + '</td></tr><tr><td>90th percentile</td><td>' + U.sig(p.p90) + '</td></tr><tr><td>Maximum</td><td>' + U.sig(p.max) + '</td></tr><tr><td>% above EPA value</td><td>' + p.pct + '%</td></tr><tr><td>Latest year</td><td>' + esc(p.yr) + '</td></tr></table><div class="small">WQP groundwater wells since 2010 · ' + U.lbl('OBSERVED') + '</div>'; }
            pop.setLngLat(e.lngLat).setHTML(html).addTo(map);
          });
          map.on('mousemove', function (e) { map.getCanvas().style.cursor = map.queryRenderedFeatures(e.point, { layers: ['sx-mx', 'sx-top', 'sx-fill'] }).length ? 'pointer' : ''; });
        });
        // GGMN toggle on this map
        var ggAdded = false;
        $('#sxGg').onchange = function () {
          var on = this.checked;
          if (!ggAdded) { ggAdded = true; U.layer('ggmn_global.json').then(function (g) { var m0 = A.map; A.map = map; try { lay('ggmn').build(g); } finally { A.map = m0; } U.setVis(map, 'ggmn-c', $('#sxGg').checked); }); }
          else U.setVis(map, 'ggmn-c', on);
        };
      }).catch(function (e) { console.warn('samples', e); $('#sxMap').innerHTML = '<p style="padding:30px">Sample layers not available: ' + esc(e.message) + '</p>'; });
    });
  }

  /* ---------- Siting ---------- */
  var ST = { w: { brackish: 0.30, produced: 0.30, stress: 0.25, demand: 0.15 }, data: null, map: null };
  var WL = { brackish: 'Brackish groundwater', produced: 'Produced-water presence', stress: 'Water stress', demand: 'Data-center demand nearby' };
  function stScore(r) { var w = ST.w, sw = w.brackish + w.produced + w.stress + w.demand || 1; return 100 * (w.brackish * r[3] + w.produced * r[4] + w.stress * r[5] + w.demand * r[6]) / sw; }
  function stRefresh() {
    var rows = ST.data.rows, sc = rows.map(function (r, i) { return { i: i, s: stScore(r) }; }).sort(function (a, b) { return b.s - a.s; });
    var rank = {}; sc.forEach(function (x, k) { rank[x.i] = k + 1; });
    var feats = rows.map(function (r, i) { return U.pt(r[1], r[0], { lat: r[0], lon: r[1], score: +stScore(r).toFixed(1), rank: rank[i], sb: r[3], sp: r[4], ss: r[5], sd: r[6], bp: r[8], swd: r[11], dc: r[13] }); });
    if (ST.map && ST.map.getSource('stc')) ST.map.getSource('stc').setData(U.fc(feats));
    var lv = ST.data.longview.cell, li = rows.findIndex(function (r) { return r[0] === lv.lat && r[1] === lv.lon; });
    var lr = rank[li], ls = stScore(rows[li]);
    $('#lvCall').innerHTML = '<h3>Longview, Texas callout ' + U.lbl('ANALYTIC ASSESSMENT') + '</h3>' +
      '<p><b>The paper</b> (' + U.srcLink('paper') + '; press release ' + U.srcLink('ut_news') + ') reports that for a Longview case study, brackish groundwater with two-stage reverse osmosis scored best of the three supply scenarios compared on its SWUI metric. It is a site-specific design comparison, not a ranking of Texas locations. Full text was not accessed.</p>' +
      '<p><b>This atlas\'s regional screen</b> ' + U.lbl('MODELED') + ': the 0.25° cell containing Longview scores <b>' + ls.toFixed(1) + '</b>, rank <b>' + lr + ' of ' + U.n(rows.length) + '</b> at the current weights (' + sc[0].s.toFixed(1) + ' is the top score). Its brackish share is ' + lv.brackish_pct + '% of ' + U.n(lv.n_nbga) + ' NBGA samples (median TDS ' + U.n(lv.nbga_median_tds) + ' mg/L), so the model sees mostly fresh groundwater there; injection/disposal wells within 50 km: ' + U.n(lv.swd_50km) + '; tracked data centers within 50 km: ' + lv.dc_50km + '; drought class at build date: D' + lv.drought_class + '.</p>' +
      '<p class="small">The two results answer different questions and are not comparable. The model was not tuned to match the paper. Use the sliders to see which weights, if any, would move Longview up.</p>';
    var top = sc.slice(0, 12);
    $('#stTop').innerHTML = '<thead><tr><th>#</th><th>Cell centre</th><th>Score</th><th>Brackish %</th><th>Disposal ≤50 km</th><th>DCs ≤50 km</th></tr></thead><tbody>' + top.map(function (x, k) { var r = rows[x.i]; return '<tr><td>' + (k + 1) + '</td><td>' + r[0].toFixed(2) + ', ' + r[1].toFixed(2) + '</td><td class="num">' + x.s.toFixed(1) + '</td><td class="num">' + r[8] + '</td><td class="num">' + U.n(r[11]) + '</td><td class="num">' + r[13] + '</td></tr>'; }).join('') + '</tbody>';
  }
  function initSiting() {
    var sl = $('#wSliders');
    sl.innerHTML = Object.keys(WL).map(function (k) { return '<div class="slider"><span>' + esc(WL[k]) + '</span><input type="range" min="0" max="100" step="5" value="' + Math.round(ST.w[k] * 100) + '" data-k="' + k + '"><output>' + ST.w[k].toFixed(2) + '</output></div>'; }).join('') + '<p class="small">Weights are normalised to sum to 1. Defaults 0.30 / 0.30 / 0.25 / 0.15.</p>';
    $$('input[type=range]', sl).forEach(function (r) { r.oninput = function () { ST.w[r.dataset.k] = r.value / 100; r.nextElementSibling.textContent = (r.value / 100).toFixed(2); if (ST.data) stRefresh(); }; });
    $('#wReset').onclick = function () { ST.w = { brackish: 0.30, produced: 0.30, stress: 0.25, demand: 0.15 }; $$('input[type=range]', sl).forEach(function (r) { r.value = ST.w[r.dataset.k] * 100; r.nextElementSibling.textContent = ST.w[r.dataset.k].toFixed(2); }); if (ST.data) stRefresh(); };
    U.layer('siting_tx.json').then(function (g) {
      ST.data = g; stRefresh();
      var inp = g.inputs, ml = '<p>' + U.lbl('MODELED') + ' ' + esc(g.label) + '. Each 0.25° Texas cell gets four sub-scores from 0 to 1; the composite is their weighted sum × 100.</p><ul class="bul">' + g.formula.map(function (f) { return '<li><code>' + esc(f) + '</code></li>'; }).join('') + '</ul>' +
        '<p><b>Inputs</b> (as of): ' + Object.keys(inp).map(function (k) { return esc(inp[k]); }).join('; ') + '. Aqueduct 4.0 Texas baseline water stress ' + g.aqueduct_texas_bws + ' (0 to 5 scale); US Drought Monitor map ' + esc(g.usdm_date) + '.</p><p><b>Caveats</b></p><ul class="bul">' + g.caveats.map(function (c) { return '<li>' + esc(c) + '</li>'; }).join('') + '<li>This is not the SWUI of the cited paper. SWUI is a published metric for comparing supply-system designs; the paper\'s equations were not accessed here. The score is a screening aid for where open data say brackish water, produced-water handling, stress and demand overlap.</li></ul><p class="small">Generated ' + esc(U.stamp(g.asof)) + '. Percentile references: ' + esc(Object.keys(g.refs).map(function (k) { return k.replace(/_/g, ' ') + ' = ' + g.refs[k]; }).join('; ')) + '.</p>';
      $('#stMethod').innerHTML = ml;
    }).catch(function (e) { $('#lvCall').textContent = 'Siting layer not available: ' + e.message; });
    U.whenVisible($('#stMap'), function () {
      Promise.all([U.layer('siting_tx.json'), U.layer('datacenters.json'), U.layer('tx_wells_grid.json')]).then(function (d) {
        var g = d[0], dcs = d[1].rows.filter(function (r) { return r.state === 'TX'; });
        var dcf = dcs.map(function (r) { return U.pt(r.lon, r.lat, { name: r.name, city: r.city, county: r.county, state: r.state, status: r.status, operator: r.operator, tenant: r.tenant, mw: r.mw_low ? U.n(r.mw_low) + ' MW' : null, cooling: [r.cooling_type, r.cooling_source].filter(Boolean).join(' / '), conf: r.loc_conf, updated: r.updated }); });
        var inj = d[2].rows.filter(function (r) { return r[5] > 0; }).map(function (r) { return U.pt(r[1], r[0], { w: r[5] }); });
        var map = U.mkMap({ id: 'stMap', center: [-99.3, 31.4], zoom: 5.1, readout: '#stReadout', sources: { sel: { type: 'geojson', data: U.fc() }, stc: { type: 'geojson', data: U.fc() }, stdc: { type: 'geojson', data: U.fc(dcf) }, stinj: { type: 'geojson', data: U.fc(inj) }, stlv: { type: 'geojson', data: U.fc([U.pt(g.longview.lon, g.longview.lat, {})]) } },
          layers: [{ id: 'sel-halo', type: 'circle', source: 'sel', paint: { 'circle-radius': 1, 'circle-opacity': 0 } },
            { id: 'st-inj', type: 'heatmap', source: 'stinj', layout: { visibility: 'none' }, paint: { 'heatmap-weight': ['interpolate', ['linear'], ['get', 'w'], 0, 0, 200, 1], 'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 4, 8, 8, 28], 'heatmap-opacity': 0.55 } },
            { id: 'st-c', type: 'circle', source: 'stc', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 6, 7, 18, 9, 34], 'circle-color': U.stepExpr('score', [30, 40, 50, 60], ['#16365e', '#1f6390', '#4cc39a', '#ffd37a', '#ff5c6c']), 'circle-opacity': 0.72, 'circle-stroke-width': 0.4, 'circle-stroke-color': '#06101c' }, metadata: { wt: 'siting' } },
            { id: 'st-dc', type: 'circle', source: 'stdc', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 2.6, 9, 6], 'circle-color': '#ffffff', 'circle-opacity': 0.9, 'circle-stroke-width': 1, 'circle-stroke-color': '#7d3cff' }, metadata: { wt: 'dcs' } },
            { id: 'st-lv', type: 'circle', source: 'stlv', paint: { 'circle-radius': 11, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 3, 'circle-stroke-color': '#f2b84b' }, metadata: { wt: 'longview' } },
            { id: 'st-lv-l', type: 'symbol', source: 'stlv', layout: { 'text-field': 'Longview', 'text-font': ['Noto Sans Bold'], 'text-size': 13, 'text-offset': [0, -1.6], 'text-anchor': 'bottom' }, paint: { 'text-color': '#f2b84b', 'text-halo-color': '#06101c', 'text-halo-width': 2 } }] });
        ST.map = map; window.__stmap = map;
        map.on('load', function () { stRefresh(); });
        $('#stLegend').innerHTML = U.legendSteps('Siting score (0 to 100)', [30, 40, 50, 60], ['#16365e', '#1f6390', '#4cc39a', '#ffd37a', '#ff5c6c'], String, 'MODELED') + '<div class="lg-row"><span class="lg-sw" style="background:#fff;border:1px solid #7d3cff"></span>Tracked Texas data center</div>';
        $('#stDc').onchange = function () { U.setVis(map, 'st-dc', this.checked); };
        $('#stSwd').onchange = function () { U.setVis(map, 'st-inj', this.checked); };
        var pop = new maplibregl.Popup({ maxWidth: '320px', offset: 10 });
        map.on('click', function (e) {
          var r = map.queryRenderedFeatures([[e.point.x - 5, e.point.y - 5], [e.point.x + 5, e.point.y + 5]], { layers: ['st-dc', 'st-lv', 'st-c'] });
          if (!r.length) { pop.remove(); return; }
          var f = r[0], t = H[f.layer.metadata.wt](f.properties), rows = (t.rows || []).filter(function (x) { return x; });
          pop.setLngLat(e.lngLat).setHTML('<div class="pp-n">' + esc(t.title) + '</div><div class="small">' + esc(t.kick) + ' ' + U.lbl(t.label) + '</div><table class="kvt">' + rows.map(function (x) { return '<tr><td>' + esc(x[0]) + '</td><td>' + esc(x[1]) + '</td></tr>'; }).join('') + '</table>' + (t.note ? '<div class="small">' + esc(t.note) + '</div>' : '')).addTo(map);
        });
      }).catch(function (e) { console.warn('siting map', e); });
    });
  }

  /* ---------- Chart builder ---------- */
  var DS = {
    states: { label: 'US states: community water systems', src: 'echo_sdwa', name: 'state', load: function () { return Promise.resolve(Object.keys(D.sdwa_state).map(function (k) { var v = D.sdwa_state[k]; return { state: k, community_systems: v.cws, population_served: v.cws_pop, health_flag_systems: v.cws_health_viol, health_flag_pct: v.cws ? +(100 * v.cws_health_viol / v.cws).toFixed(2) : 0, serious_violators: v.cws_serious, groundwater_systems: v.cws_gw, surface_water_systems: v.cws_sw, pop_per_system: v.cws ? Math.round(v.cws_pop / v.cws) : 0, small_nontransient: v.ntnc, transient: v.tnc }; }).filter(function (r) { return r.community_systems > 0; })); } },
    basins: { label: 'Produced-water chemistry by basin (USGS PWDB)', src: 'pwdb', name: 'basin', load: function () { return Promise.resolve(D.pwdb_basins.map(function (b) { return { basin: b.basin, samples: b.n_samples, tds_samples: b.n_tds, tds_median_mgL: b.tds_median_mgL, tds_p10_mgL: b.tds_p10_mgL, tds_p90_mgL: b.tds_p90_mgL, chloride_median_mgL: b.cl_median_mgL, lithium_median_mgL: b.li_median_mgL, bromide_median_mgL: b.br_median_mgL }; })); } },
    siting: { label: 'Texas siting cells (MODELED)', src: 'paper', name: null, load: function () { return U.layer('siting_tx.json').then(function (g) { return g.rows.map(function (r) { return { lat: r[0], lon: r[1], score: r[2], brackish_score: r[3], produced_score: r[4], stress_score: r[5], demand_score: r[6], nbga_samples: r[7], brackish_pct: r[8], nbga_median_tds: r[9], pw_tds_median: r[10], disposal_wells_50km: r[11], commercial_disposal_50km: r[12], data_centers_50km: r[13], quakes_m3_5y_50km: r[15], rank: r[17] }; }); }); } },
    ggmn: { label: 'IGRAC GGMN registry by country', src: 'igrac', name: 'country', load: function () { return U.layer('ggmn_global.json').then(function (g) { return Object.keys(g.countries).map(function (k) { var v = g.countries[k]; return { country: k, registered_points: v.sites, with_level_series: v.level, with_quality_series: v.quality, springs: v.springs }; }); }); } },
    mxaq: { label: 'Mexico aquifers (CONAGUA)', src: 'conagua', name: 'name', load: function () { return U.layer('mx_aquifers.geojson').then(function (g) { return g.features.map(function (f) { var p = f.properties; return { name: p.name, state: p.state, area_km2: p.area_km2, recharge_hm3: p.recharge_hm3, concessioned_hm3: p.concessioned_hm3, availability_hm3: p.avail_hm3, deficit_hm3: p.deficit_hm3 }; }); }); } },
    mxplants: { label: 'Mexico treatment plants by state (CONAGUA)', src: 'conagua', name: 'state', load: function () { return U.layer('mx_plants.json').then(function (g) { var o = []; Object.keys(g.wastewater_by_state).forEach(function (k) { var w = g.wastewater_by_state[k], p = (g.potabilization_by_state || {})[k] || {}; o.push({ state: k, wastewater_plants: w.n, wastewater_capacity_lps: w.cap_lps, wastewater_treated_lps: w.flow_lps, potab_plants: p.n || 0, potab_capacity_lps: p.cap_lps || 0 }); }); return o; }); } },
    wser: { label: 'Canada wastewater systems by province (ECCC WSER)', src: 'wser', name: 'province', load: function () { return U.layer('ca_wser.json').then(function (g) { return Object.keys(g.by_province).map(function (k) { return { province: k, systems: g.by_province[k].n, effluent_m3_per_day: Math.round(g.by_province[k].vol_m3d) }; }); }); } },
    nbga: { label: 'Brackish groundwater cells (USGS NBGA)', src: 'nbga', name: null, load: function () { return U.layer('nbga_grid.json').then(function (g) { return g.rows.map(function (r) { return { lat: r[0], lon: r[1], samples: r[2], median_tds_mgL: r[3], brackish_pct: r[4], fresh_pct: r[5], saline_pct: r[6], median_depth_ft: r[7], state: r[8] }; }); }); } }
  };
  var PRESETS = [
    ['States: share of community systems with a health-based flag', { ds: 'states', type: 'bar', x: 'state', y: 'health_flag_pct', top: 20 }],
    ['Produced-water TDS by basin', { ds: 'basins', type: 'bar', x: 'basin', y: 'tds_median_mgL', top: 20, log: true }],
    ['Siting: score vs disposal wells', { ds: 'siting', type: 'scatter', x: 'disposal_wells_50km', y: 'score' }],
    ['GGMN registered points by country', { ds: 'ggmn', type: 'bar', x: 'country', y: 'registered_points', top: 20, log: true }],
    ['Mexico aquifers: recharge vs deficit', { ds: 'mxaq', type: 'scatter', x: 'recharge_hm3', y: 'deficit_hm3' }],
    ['Canada wastewater effluent by province', { ds: 'wser', type: 'bar', x: 'province', y: 'effluent_m3_per_day', top: 20 }]
  ];
  var CB = { ds: 'states', type: 'bar', x: 'state', y: 'health_flag_pct', top: 20, log: false, rows: {} };
  function cbFields(rows) { var f = Object.keys(rows[0] || {}); return { all: f, num: f.filter(function (k) { return typeof rows[0][k] === 'number'; }), cat: f.filter(function (k) { return typeof rows[0][k] !== 'number'; }) }; }
  function cbControls(rows) {
    var F = cbFields(rows), o = function (arr, v) { return arr.map(function (k) { return '<option' + (k === v ? ' selected' : '') + '>' + esc(k) + '</option>'; }).join(''); };
    var dsOpts = Object.keys(DS).map(function (k) { return '<option value="' + k + '"' + (k === CB.ds ? ' selected' : '') + '>' + esc(DS[k].label) + '</option>'; }).join('');
    $('#cbControls').innerHTML = '<label>Dataset<select id="cbDs">' + dsOpts + '</select></label><div class="cb-types" id="cbTypes">' + ['bar', 'scatter', 'histogram'].map(function (t) { return '<button data-t="' + t + '" class="' + (CB.type === t ? 'on' : '') + '">' + t + '</button>'; }).join('') + '</div>' +
      '<label>X<select id="cbX">' + o(CB.type === 'bar' ? F.all : F.num, CB.x) + '</select></label><label id="cbYl">Y (numeric)<select id="cbY">' + o(F.num, CB.y) + '</select></label>' +
      '<label>Top N (bar)<select id="cbTop">' + [10, 20, 40, 100].map(function (n) { return '<option' + (n === CB.top ? ' selected' : '') + '>' + n + '</option>'; }).join('') + '</select></label><label class="chk"><input type="checkbox" id="cbLog"' + (CB.log ? ' checked' : '') + '> Log scale (Y)</label>' +
      '<div class="small">Source: ' + U.srcLink(DS[CB.ds].src) + '</div><button class="btn ghost" id="cbCsv">⬇ CSV of dataset</button>';
    $('#cbDs').onchange = function () { CB.ds = this.value; var d = DS[CB.ds]; loadDs().then(function (rows) { var F2 = cbFields(rows); CB.x = d.name || F2.num[0]; CB.y = F2.num.filter(function (k) { return k !== CB.x; })[0]; CB.type = d.name ? 'bar' : 'scatter'; if (!d.name) CB.x = F2.num[0]; cbControls(rows); cbRender(); }); };
    $$('#cbTypes button').forEach(function (b) { b.onclick = function () { CB.type = b.dataset.t; var F2 = cbFields(CB.rows[CB.ds]); if (CB.type !== 'bar' && F2.num.indexOf(CB.x) < 0) CB.x = F2.num[0]; cbControls(CB.rows[CB.ds]); cbRender(); }; });
    ['cbX', 'cbY', 'cbTop'].forEach(function (id) { $('#' + id).onchange = function () { CB.x = $('#cbX').value; CB.y = $('#cbY').value; CB.top = +$('#cbTop').value; cbRender(); }; });
    $('#cbLog').onchange = function () { CB.log = this.checked; cbRender(); };
    $('#cbCsv').onclick = function () { var r = CB.rows[CB.ds]; U.download('poseidon_' + CB.ds + '.csv', U.toCSV(r, Object.keys(r[0])), 'text/csv'); };
    $('#cbYl').style.display = CB.type === 'histogram' ? 'none' : '';
  }
  function loadDs() { if (CB.rows[CB.ds]) return Promise.resolve(CB.rows[CB.ds]); return DS[CB.ds].load().then(function (r) { CB.rows[CB.ds] = r; return r; }); }
  function cbRender() {
    var rows = CB.rows[CB.ds], ch = U.chart('chart'); if (!rows || !ch) return;
    var d = DS[CB.ds], opt, title = '', yU = CB.log ? 'log' : 'value';
    if (CB.type === 'bar') {
      var r = rows.filter(function (x) { return typeof x[CB.y] === 'number'; }).sort(function (a, b) { return b[CB.y] - a[CB.y]; }).slice(0, CB.top);
      var cat = function (x) { return d.name && CB.x === d.name ? x[d.name] : (x[CB.x] + (d.name ? ' · ' + x[d.name] : '')); };
      opt = { tooltip: Object.assign({}, U.TIP, { trigger: 'axis', axisPointer: { type: 'shadow' } }), grid: { left: 60, right: 20, top: 38, bottom: 90 }, xAxis: Object.assign({ type: 'category', data: r.map(cat), axisLabel: { color: '#a3b2c8', rotate: 40, interval: 0, fontSize: 10 } }, {}), yAxis: Object.assign({ type: yU, name: CB.y }, U.AX), dataZoom: [{ type: 'inside' }], series: [{ type: 'bar', data: r.map(function (x) { return x[CB.y]; }), itemStyle: { color: '#38c7ff' } }] };
      title = CB.y + ' by ' + (d.name || CB.x) + ' (top ' + r.length + ')';
    } else if (CB.type === 'scatter') {
      var pts = rows.filter(function (x) { return typeof x[CB.x] === 'number' && typeof x[CB.y] === 'number'; });
      opt = { tooltip: Object.assign({}, U.TIP, { formatter: function (p) { var x = pts[p.dataIndex]; return (d.name ? '<b>' + esc(x[d.name]) + '</b><br>' : '') + esc(CB.x) + ': ' + U.sig(x[CB.x]) + '<br>' + esc(CB.y) + ': ' + U.sig(x[CB.y]); } }), grid: { left: 64, right: 24, top: 38, bottom: 44 }, xAxis: Object.assign({ type: 'value', name: CB.x, nameLocation: 'middle', nameGap: 28, scale: true }, U.AX), yAxis: Object.assign({ type: yU, name: CB.y, scale: true }, U.AX), dataZoom: [{ type: 'inside' }], series: [{ type: 'scatter', symbolSize: 6, data: pts.map(function (x) { return [x[CB.x], x[CB.y]]; }), itemStyle: { color: '#38c7ff', opacity: 0.6 }, large: true }] };
      title = CB.y + ' vs ' + CB.x + ' (' + U.n(pts.length) + ' records)';
    } else {
      var v = rows.map(function (x) { return x[CB.x]; }).filter(function (x) { return typeof x === 'number' && isFinite(x) && (!CB.log || x > 0); }), mn = Math.min.apply(null, v), mx = Math.max.apply(null, v), nb = 24, bins = new Array(nb).fill(0), lo = CB.log ? Math.log10(mn) : mn, hi = CB.log ? Math.log10(mx) : mx, w = (hi - lo) / nb || 1;
      v.forEach(function (x) { var t = CB.log ? Math.log10(x) : x, i = Math.min(nb - 1, Math.floor((t - lo) / w)); bins[i]++; });
      var labels = bins.map(function (_, i) { var a = lo + i * w; return U.sig(CB.log ? Math.pow(10, a) : a); });
      opt = { tooltip: Object.assign({}, U.TIP, { trigger: 'axis' }), grid: { left: 60, right: 20, top: 20, bottom: 60 }, xAxis: Object.assign({ type: 'category', data: labels, name: CB.x + (CB.log ? ' (log bins)' : ''), nameLocation: 'middle', nameGap: 40, axisLabel: { color: '#a3b2c8', fontSize: 10, rotate: 30 } }, {}), yAxis: Object.assign({ type: 'value', name: 'records' }, U.AX), series: [{ type: 'bar', data: bins, itemStyle: { color: '#5b8def' }, barCategoryGap: '4%' }] };
      title = 'Distribution of ' + CB.x + ' (' + U.n(v.length) + ' records)';
    }
    ch.setOption(opt, true);
    $('#cbTitle').textContent = d.label + ': ' + title;
    $('#cbNote').innerHTML = 'Source: ' + U.srcLink(d.src) + ' · ' + U.lbl(CB.ds === 'siting' ? 'MODELED' : 'OBSERVED') + ' Values are the layer values; nothing is smoothed or imputed.';
  }
  function initCharts() {
    $('#presets').innerHTML = PRESETS.map(function (p, i) { return '<button data-i="' + i + '">' + esc(p[0]) + '</button>'; }).join('');
    $$('#presets button').forEach(function (b) { b.onclick = function () { var p = PRESETS[+b.dataset.i][1]; Object.assign(CB, { ds: p.ds, type: p.type, x: p.x, y: p.y || CB.y, top: p.top || 20, log: !!p.log }); loadDs().then(function (r) { cbControls(r); cbRender(); $$('#presets button').forEach(function (x) { x.classList.toggle('on', x === b); }); }); }; });
    U.whenVisible($('#chart'), function () { loadDs().then(function (r) { cbControls(r); cbRender(); $('#presets button').classList.add('on'); }); });
  }

  function boot() { initFlow(); initOilGas(); initSamples(); initSiting(); initCharts(); }
  if (A.ready) boot(); else document.addEventListener('wt-ready', boot);
})();
