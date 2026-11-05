/* Poseidon NARINT WATINT atlas: main map behaviour, KPIs, intel, network, register, findings, method, sources. */
(function () {
  'use strict';
  var U = window.WTU, D = U.D, G = U.G, $ = U.$, $$ = U.$$, esc = U.esc, REF = D.ref, A = window.WTApp, H = A.H, LAYERS = A.LAYERS;
  var map, mapReady = false, base = 'dark', measuring = false, mpts = [], mcursor = null, hoverPop, searchPin = null;
  var S = { on: {}, sel: null };
  var OPT = { ref: true };

  function renderLayerList() {
    var html = '', last = '';
    LAYERS.forEach(function (L) {
      if (L.grp !== last) { html += '<div class="lg-grp">' + esc(L.grp) + '</div>'; last = L.grp; }
      html += '<label class="lyr"><input type="checkbox" data-l="' + L.id + '"' + (L.on ? ' checked' : '') + '><span>' + esc(L.label) + ' <span class="lbl ' + esc(L.tag.split(' ')[0]) + '">' + esc(L.tag) + '</span>' + (L.note ? '<small>' + esc(L.note) + '</small>' : '') + '</span></label>';
    });
    $('#layerList').innerHTML = html;
    $$('#layerList input').forEach(function (cb) { cb.onchange = function () { setLayer(cb.dataset.l, cb.checked); }; });
  }
  function byId(id) { return LAYERS.filter(function (l) { return l.id === id; })[0]; }
  function setLayer(id, on) {
    var L = byId(id); S.on[id] = on;
    var cb = $('#layerList input[data-l="' + id + '"]'); if (cb) cb.checked = on;
    if (!mapReady) { renderLegend(); return; }
    if (on && !L.loaded) {
      L.loaded = 'loading';
      Promise.resolve(L.load()).then(function (d) { L.build(d); L.loaded = true; L.ids.forEach(function (i) { U.setVis(map, i, !!S.on[id]); }); applyOrder(); renderLegend(); })
        .catch(function (e) { L.loaded = false; console.warn('layer ' + id, e); U.toast('Could not load ' + L.label); var c = $('#layerList input[data-l="' + id + '"]'); if (c) c.checked = false; S.on[id] = false; renderLegend(); });
    } else if (L.loaded === true) L.ids.forEach(function (i) { U.setVis(map, i, on); });
    renderLegend();
  }
  function applyOrder() { ['sel-halo', 'measure-line', 'measure-pts'].forEach(function (id) { if (map.getLayer(id)) map.moveLayer(id); }); }
  function renderLegend() {
    var h = '';
    LAYERS.forEach(function (L) { if (S.on[L.id]) h += '<div class="lg-blk">' + L.legend.call(L) + '</div>'; });
    $('#legendBody').innerHTML = h || '<div class="small">No layers on.</div>';
  }

  function initMap() {
    if (!window.maplibregl) { $('#mapcv').innerHTML = '<p style="padding:40px">Map library failed to load.</p>'; return; }
    var st = U.baseStyle();
    st.sources.sel = { type: 'geojson', data: U.fc() }; st.sources.measure = { type: 'geojson', data: U.fc() };
    st.layers.push({ id: 'sel-halo', type: 'circle', source: 'sel', paint: { 'circle-radius': 15, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': '#38c7ff', 'circle-stroke-width': 2.4 } });
    st.layers.push({ id: 'measure-line', type: 'line', source: 'measure', filter: ['==', ['geometry-type'], 'LineString'], paint: { 'line-color': '#ffb547', 'line-width': 2.4, 'line-dasharray': [2, 1.2] } });
    st.layers.push({ id: 'measure-pts', type: 'circle', source: 'measure', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 4.5, 'circle-color': '#ffb547', 'circle-stroke-color': '#070b13', 'circle-stroke-width': 1.5 } });
    var mobile = window.innerWidth < 820;
    map = new maplibregl.Map({ container: 'mapcv', style: st, center: mobile ? [-100, 38] : [-60, 28], zoom: mobile ? 1.6 : 2.15, maxPitch: 75, attributionControl: { compact: true }, fadeDuration: 120 });
    A.map = map; window.__wtmap = map;
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    map.addControl(new maplibregl.FullscreenControl({ container: $('#mapwrap') }), 'top-right');
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric', maxWidth: 130 }), 'bottom-left');
    map.addControl(new maplibregl.ScaleControl({ unit: 'nautical', maxWidth: 130 }), 'bottom-left');
    hoverPop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, maxWidth: '300px', offset: 12 });
    map.on('load', function () {
      mapReady = true; U.setBase(map, base, OPT.ref);
      LAYERS.forEach(function (L) { if (S.on[L.id]) { S.on[L.id] = false; setLayer(L.id, true); } });
      renderLegend();
    });
    map.on('error', function (e) { if (e && e.error && !/tile|Failed to fetch|AJAXError|NetworkError|Load failed/i.test(String(e.error.message || e.error))) console.warn('map', e.error); });
    function interactive() {
      var out = [];
      LAYERS.forEach(function (L) { if (L.loaded === true && S.on[L.id]) (L.hi || []).forEach(function (i) { if (map.getLayer(i)) out.push(i); }); });
      return out;
    }
    function hit(e, pad) {
      var ly = interactive(); if (!ly.length) return null;
      var r = map.queryRenderedFeatures([[e.point.x - pad, e.point.y - pad], [e.point.x + pad, e.point.y + pad]], { layers: ly });
      r.sort(function (a, b) { return (a.geometry.type === 'Point' ? 0 : 1) - (b.geometry.type === 'Point' ? 0 : 1); });
      return r[0] || null;
    }
    map.on('mousemove', function (e) {
      U.readout(map, '#readout', e.lngLat);
      if (measuring) { if (mpts.length) { mcursor = [e.lngLat.lng, e.lngLat.lat]; measureRender(); } return; }
      var f = hit(e, 3);
      if (f) { map.getCanvas().style.cursor = 'pointer'; var t = detailFor(f, e.lngLat); hoverPop.setLngLat(e.lngLat).setHTML('<div class="pp-n">' + esc(t.title) + '</div><div class="small">' + esc(t.kick) + '</div>').addTo(map); }
      else { map.getCanvas().style.cursor = ''; hoverPop.remove(); }
    });
    map.on('click', function (e) {
      if (measuring) { mpts.push([e.lngLat.lng, e.lngLat.lat]); measureRender(); return; }
      var f = hit(e, 5);
      if (f) showDetail(detailFor(f, e.lngLat), f, e.lngLat); else closeDetail();
    });
    map.on('moveend', function (e) { if (!e.originalEvent || e.originalEvent.type.indexOf('touch') === 0) U.readout(map, '#readout', map.getCenter(), 'Centre'); });
    var fixing = false;
    function groundFix() {
      if (fixing || !map.getTerrain()) return;
      var el = map.queryTerrainElevation(map.getCenter());
      if (el === null || el === undefined || Math.abs(el - (map.getCenterElevation ? map.getCenterElevation() : 0)) < 25) return;
      fixing = true; map.jumpTo({ center: map.getCenter(), elevation: el }); fixing = false;
    }
    map.on('moveend', function () { setTimeout(groundFix, 50); }); map.on('idle', groundFix);

    $$('#baseSeg button').forEach(function (b) { b.onclick = function () { base = b.dataset.b; $$('#baseSeg button').forEach(function (x) { x.classList.toggle('on', x === b); }); U.setBase(map, base, OPT.ref); }; });
    $('#baseSeg button[data-b="dark"]').classList.add('on');
    $('#lRef').onchange = function () { OPT.ref = this.checked; U.setBase(map, base, OPT.ref); };
    $('#lHill').onchange = function () { U.setVis(map, 'hill', this.checked); };
    $('#l3d').onchange = function () {
      if (this.checked) { map.setTerrain({ source: 'dem', exaggeration: 1.4 }); map.easeTo({ pitch: 55 }); } else { map.setTerrain(null); map.easeTo({ pitch: 0 }); }
    };
    $('#lGlobe').onchange = function () { map.setProjection({ type: this.checked ? 'globe' : 'mercator' }); };
    $('#measureBtn').onclick = function () { toggleMeasure(!measuring); };
    $('#homeBtn').onclick = function () { flyRegion('world'); };
    $('#expGeo').onclick = exportGeo; $('#expCsv').onclick = exportCsv;
    $('#layersHead').onclick = function () { $('#layersPanel').classList.toggle('closed'); };
    $('#legendHead').onclick = function () { $('#legend').classList.toggle('closed'); };
    if (mobile) { $('#layersPanel').classList.add('closed'); $('#legend').classList.add('closed'); $('#readout').textContent = 'Pan the map to read the centre coordinate'; }
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { if (measuring) toggleMeasure(false); closeDetail(); } });
    initSearch();
  }
  function flyRegion(k) {
    var r = REF.regions[k]; if (!r || !map) return;
    var z = r.zoom; if (window.innerWidth < 820) z = Math.max(0.8, z - 0.9);
    map.flyTo({ center: r.center, zoom: z, pitch: 0, bearing: 0, duration: 1200 });
  }
  A.flyRegion = flyRegion; A.setLayer = setLayer; A.S = S;

  function detailFor(f) {
    var key = (f.layer.metadata && f.layer.metadata.wt) || '', p = f.properties, h = H[key];
    if (!h) return { title: key, kick: '', rows: [] };
    var t = h(p); t.key = key; return t;
  }
  function coordOf(f, ll) { return f.geometry.type === 'Point' ? { lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1] } : { lon: ll.lng, lat: ll.lat }; }
  function stampOrText(s) { return s ? (/^\d{4}-\d\d-\d\dT/.test(s) ? U.stamp(s) : s) : 'n/a'; }
  function showDetail(t, f, ll) {
    var c = coordOf(f, ll), d = $('#detail');
    map.getSource('sel').setData(f.geometry.type === 'Point' ? U.fc([U.pt(c.lon, c.lat)]) : U.fc());
    var s = t.src && D.sources[t.src], rows = (t.rows || []).filter(function (r) { return r; }), prec = REF.precision[t.prec];
    d.innerHTML = '<button class="d-close" id="dClose" aria-label="Close">×</button><div class="d-kick">' + esc(t.kick || '') + '</div><div class="d-name">' + esc(t.title) + '</div><div class="tags">' + (t.label ? U.lbl(t.label) : '') + (prec ? '<span class="tag">' + esc(t.prec + ' · ' + prec.label) + '</span>' : '') + '</div>' +
      (rows.length ? '<table class="kvt">' + rows.map(function (r) { return '<tr><td>' + esc(r[0]) + '</td><td>' + esc(r[1]) + '</td></tr>'; }).join('') + '</table>' : '') + (t.html || '') +
      (t.note ? '<p class="small">' + esc(t.note) + '</p>' : '') +
      '<div class="d-sec"><h4>Position (WGS 84)</h4><div class="mono">' + G.fmtDD(c.lat, c.lon, 5) + '<br>' + G.fmtDMS(c.lat, c.lon) + '<br>MGRS ' + G.mgrs(c.lat, c.lon) + '</div>' + (prec ? '<div class="small">Nominal circular error about ' + U.n(prec.ce_m) + ' m. ' + esc(prec.desc) + '</div>' : '') + '<button class="btn ghost copy" id="dCopy">Copy lat, lon</button></div>' +
      '<div class="d-sec"><h4>Source</h4><div class="small">' + (s ? '<a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.name) + '</a><br>' : '') + 'As of ' + esc(stampOrText(t.asof)) + '</div></div>' +
      ((t.links || []).length ? '<div class="links">' + t.links.map(function (l) { return '<a href="' + esc(l[1]) + '" target="_blank" rel="noopener">' + esc(l[0]) + '</a>'; }).join('') + '</div>' : '');
    d.hidden = false;
    $('#dClose').onclick = closeDetail;
    $('#dCopy').onclick = function () { var txt = c.lat.toFixed(5) + ', ' + c.lon.toFixed(5); if (navigator.clipboard) navigator.clipboard.writeText(txt); U.toast('Copied ' + txt); };
    S.sel = t.key;
  }
  function closeDetail() { $('#detail').hidden = true; if (map && map.getSource('sel')) map.getSource('sel').setData(U.fc()); S.sel = null; }

  function measureRender() {
    var coords = mpts.slice(); if (mcursor && mpts.length) coords.push(mcursor);
    var f = mpts.map(function (p) { return { type: 'Feature', geometry: { type: 'Point', coordinates: p }, properties: {} }; });
    if (coords.length > 1) {
      var line = [];
      for (var i = 1; i < coords.length; i++) { var seg = G.gcPath(coords[i - 1], coords[i], 32); line = line.concat(i > 1 ? seg.slice(1) : seg); }
      f.push({ type: 'Feature', geometry: { type: 'LineString', coordinates: line }, properties: {} });
    }
    map.getSource('measure').setData(U.fc(f));
    var box = $('#measureBox');
    if (!measuring) { box.hidden = true; return; }
    var km = 0; for (var j = 1; j < coords.length; j++) km += G.havKm(coords[j - 1], coords[j]);
    var brg = coords.length > 1 ? G.bearing(coords[coords.length - 2], coords[coords.length - 1]) : null;
    box.hidden = false;
    box.innerHTML = '<span>📏 ' + (mpts.length ? '<b>' + km.toFixed(km < 10 ? 2 : 1) + ' km</b> · ' + (km / 1.852).toFixed(1) + ' nmi · ' + (km / 1.609344).toFixed(1) + ' mi' + (brg !== null ? ' · brg ' + brg.toFixed(1) + '°' : '') + ' · ' + mpts.length + ' pts' : 'Click to place the first point') + '</span>' +
      '<button class="btn ghost" id="mUndo">Undo</button><button class="btn ghost" id="mClear">Clear</button><button class="btn" id="mDone">Done</button>';
    $('#mUndo').onclick = function () { mpts.pop(); measureRender(); };
    $('#mClear').onclick = function () { mpts = []; measureRender(); };
    $('#mDone').onclick = function () { toggleMeasure(false); };
  }
  function toggleMeasure(on) {
    measuring = on; mcursor = null; if (!on) mpts = [];
    $('#measureBtn').classList.toggle('on', on);
    map.getCanvas().style.cursor = on ? 'crosshair' : '';
    if (on) map.doubleClickZoom.disable(); else map.doubleClickZoom.enable();
    if (hoverPop) hoverPop.remove();
    measureRender();
  }

  function viewFeatures() {
    var out = [], b = map.getBounds(), seen = {};
    LAYERS.forEach(function (L) {
      if (!S.on[L.id] || L.loaded !== true) return;
      (L.hi || []).forEach(function (lid) {
        if (!map.getLayer(lid) || seen[lid]) return; seen[lid] = 1;
        var lay = map.getLayer(lid), feats = map.querySourceFeatures(lay.source), done = {}, wt = (lay.metadata || {}).wt;
        feats.forEach(function (f) {
          if (f.geometry.type !== 'Point') return;
          var c = f.geometry.coordinates; if (c[0] < b.getWest() || c[0] > b.getEast() || c[1] < b.getSouth() || c[1] > b.getNorth()) return;
          var k = L.id + c.join(',') + JSON.stringify(f.properties).slice(0, 80); if (done[k]) return; done[k] = 1;
          var p = {}; Object.keys(f.properties).forEach(function (q) { if (!/^(arts|cats)$/.test(q)) p[q] = f.properties[q]; });
          p.layer = L.id; p.precision_class = H[wt] ? (H[wt](f.properties).prec || '') : '';
          out.push({ lon: c[0], lat: c[1], props: p });
        });
      });
    });
    return out;
  }
  function exportGeo() {
    var v = viewFeatures(); if (!v.length) { U.toast('No point features of enabled layers in view'); return; }
    var f = v.map(function (x) { x.props.mgrs = G.mgrs(x.lat, x.lon); return { type: 'Feature', geometry: { type: 'Point', coordinates: [x.lon, x.lat] }, properties: x.props }; });
    U.download('poseidon_watint_view.geojson', JSON.stringify(U.fc(f)), 'application/geo+json'); U.toast(v.length + ' features exported');
  }
  function exportCsv() {
    var v = viewFeatures(); if (!v.length) { U.toast('No point features of enabled layers in view'); return; }
    var cols = ['layer', 'lat', 'lon', 'mgrs', 'precision_class'], extra = {};
    v.forEach(function (x) { Object.keys(x.props).forEach(function (k) { if (cols.indexOf(k) < 0) extra[k] = 1; }); });
    cols = cols.concat(Object.keys(extra));
    var rows = v.map(function (x) { var r = x.props; r.lat = x.lat.toFixed(5); r.lon = x.lon.toFixed(5); r.mgrs = G.mgrs(x.lat, x.lon); return r; });
    U.download('poseidon_watint_view.csv', U.toCSV(rows, cols), 'text/csv'); U.toast(v.length + ' rows exported');
  }

  var IDX = null;
  function norm(s) { return String(s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }
  function buildIndex() {
    if (IDX) return IDX;
    IDX = Promise.all([U.layer('datacenters.json'), U.layer('ca_dwa.json'), U.layer('npdes_majors.json'), U.layer('ca_wser.json')]).then(function (d) {
      var o = [];
      d[0].rows.forEach(function (r) { o.push({ n: r.name, sub: 'Data center · ' + [r.city, r.state].filter(Boolean).join(', ') + ' · ' + r.status, lat: r.lat, lon: r.lon, z: 11 }); });
      d[1].active.forEach(function (r) { o.push({ n: r.community, sub: 'Canada advisory · ' + r.system, lat: r.lat, lon: r.lon, z: 11 }); });
      d[2].rows.forEach(function (r) { o.push({ n: r[2], sub: 'NPDES major · ' + r[4] + ' · ' + r[3], lat: r[1], lon: r[0], z: 12 }); });
      d[3].rows.forEach(function (r) { o.push({ n: r[2], sub: 'WSER system · ' + r[5], lat: r[1], lon: r[0], z: 12 }); });
      Object.keys(REF.regions).forEach(function (k) { o.push({ n: k.charAt(0).toUpperCase() + k.slice(1), sub: 'Region', lat: REF.regions[k].center[1], lon: REF.regions[k].center[0], z: REF.regions[k].zoom }); });
      o.forEach(function (x) { x.k = norm(x.n + ' ' + x.sub); });
      return o;
    });
    return IDX;
  }
  function parseLL(q) {
    var m = q.match(/^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$/);
    if (!m) return null; var a = +m[1], b = +m[2]; if (Math.abs(a) <= 90 && Math.abs(b) <= 180) return { lat: a, lon: b }; return null;
  }
  function goTo(lat, lon, z, label) {
    if (!searchPin) searchPin = new maplibregl.Marker({ color: '#38c7ff' });
    searchPin.setLngLat([lon, lat]).addTo(map);
    map.flyTo({ center: [lon, lat], zoom: z || 9, duration: 1100 });
    $('#readout').textContent = (label ? label + '  |  ' : '') + lat.toFixed(5) + ', ' + lon.toFixed(5) + '  |  MGRS ' + G.mgrs(lat, lon);
  }
  function initSearch() {
    var inp = $('#search'), list = $('#searchList'), res = [], act = -1;
    function render() {
      if (!res.length) { list.hidden = true; return; }
      list.innerHTML = res.map(function (r, i) { return '<div class="' + (i === act ? 'act' : '') + '" data-i="' + i + '">' + esc(r.n) + '<span class="sub">' + esc(r.sub) + '</span></div>'; }).join(''); list.hidden = false;
      $$('div', list).forEach(function (el) { el.onmousedown = function (e) { e.preventDefault(); pick(res[+el.dataset.i]); }; });
    }
    function pick(r) { list.hidden = true; inp.value = r.n || ''; goTo(r.lat, r.lon, r.z, r.n); }
    function run() {
      var q = inp.value.trim(); if (q.length < 2) { res = []; render(); return; }
      var ll = parseLL(q); if (ll) { res = [{ n: ll.lat + ', ' + ll.lon, sub: 'Coordinate', lat: ll.lat, lon: ll.lon, z: 10 }]; render(); return; }
      buildIndex().then(function (ix) { var k = norm(q); res = ix.filter(function (x) { return x.k.indexOf(k) >= 0; }).slice(0, 9); act = -1; render(); }).catch(function () { res = []; render(); });
    }
    inp.oninput = run; inp.onfocus = function () { buildIndex().catch(function () { }); };
    inp.onkeydown = function (e) { if (e.key === 'ArrowDown') { act = Math.min(res.length - 1, act + 1); render(); e.preventDefault(); } else if (e.key === 'ArrowUp') { act = Math.max(0, act - 1); render(); e.preventDefault(); } else if (e.key === 'Enter' && res.length) { pick(res[Math.max(0, act)]); } else if (e.key === 'Escape') { list.hidden = true; } };
    inp.onblur = function () { setTimeout(function () { list.hidden = true; }, 150); };
    $('#fGoBtn').onclick = function () { var ll = parseLL($('#fGo').value); if (ll) goTo(ll.lat, ll.lon, 10); else U.toast('Enter decimal "lat, lon"'); };
    $('#fGo').onkeydown = function (e) { if (e.key === 'Enter') $('#fGoBtn').click(); };
  }

  function sumRec(suffix) { return (D.meta.layers || []).reduce(function (t, x) { return t + (x.id.slice(-suffix.length) === suffix && x.id.indexOf('og_') !== 0 ? (x.records || 0) : 0); }, 0); }
  function renderKPIs() {
    var L = {}; D.meta.layers.forEach(function (x) { L[x.id] = x; });
    var st = D.sdwa_state, cws = 0, hv = 0; Object.keys(st).forEach(function (k) { cws += st[k].cws; hv += st[k].cws_health_viol; });
    var k = [
      [U.n(sumRec('_wells_grid')), 'Oil and gas well records', 'TX, NM, OK, AB, BC, SK regulators'],
      [U.n(sumRec('_swd')), 'Injection / disposal records', 'Volumes published for NM and OK only'],
      [U.n(cws), 'US community water systems', U.n(hv) + ' carry the health-based violation flag'],
      [U.n(L.npdes_majors && L.npdes_majors.records), 'Major NPDES dischargers', 'EPA ECHO, ' + U.date(L.npdes_majors && L.npdes_majors.asof)],
      [U.n(L.ggmn_global && L.ggmn_global.records), 'GGMN registry points', 'IGRAC; not a complete global set'],
      [U.n(L.datacenters && L.datacenters.records), 'Data centers tracked (US)', 'FracTracker; no water-use data']
    ];
    $('#kpis').innerHTML = k.map(function (x, i) { return '<div class="kpi' + (i === 1 ? ' warn' : '') + '"><b>' + esc(x[0]) + '</b><span>' + esc(x[1]) + '</span><small>' + esc(x[2]) + '</small></div>'; }).join('');
    $('#bnAsof').textContent = 'WGS 84 · built ' + U.date(D.meta.built_at);
  }

  var CATS = { produced_water: 'Produced water', data_center: 'Data center water', contamination: 'Contamination', drought: 'Drought', infrastructure: 'Infrastructure', regulatory: 'Regulatory', hazard: 'GDACS hazard' };
  var IS = { win: 30, cat: null, reg: null };
  function ageDays(it) { var t = Date.parse(it.date || ''); return isNaN(t) ? 9999 : (Date.now() - t) / 864e5; }
  function intelItems() { return D.updates.filter(function (it) { return ageDays(it) <= IS.win && (!IS.cat || it.category === IS.cat) && (!IS.reg || (it.regions || []).indexOf(IS.reg) >= 0); }); }
  function renderIntel() {
    var all = D.updates.filter(function (it) { return ageDays(it) <= IS.win; });
    var cats = {}, regs = {}; all.forEach(function (it) { cats[it.category] = (cats[it.category] || 0) + 1; (it.regions || []).forEach(function (r) { regs[r] = (regs[r] || 0) + 1; }); });
    $('#iCats').innerHTML = '<button class="chip' + (!IS.cat ? ' on' : '') + '" data-c="">All ' + all.length + '</button>' + Object.keys(cats).sort(function (a, b) { return cats[b] - cats[a]; }).map(function (c) { return '<button class="chip' + (IS.cat === c ? ' on' : '') + '" data-c="' + c + '">' + esc(CATS[c] || c) + ' ' + cats[c] + '</button>'; }).join('');
    $('#iRegs').innerHTML = Object.keys(regs).sort(function (a, b) { return regs[b] - regs[a]; }).slice(0, 8).map(function (r) { return '<button class="chip' + (IS.reg === r ? ' on' : '') + '" data-r="' + esc(r) + '">' + esc(r) + ' ' + regs[r] + '</button>'; }).join('');
    $$('#iCats .chip').forEach(function (b) { b.onclick = function () { IS.cat = b.dataset.c || null; renderIntel(); }; });
    $$('#iRegs .chip').forEach(function (b) { b.onclick = function () { IS.reg = IS.reg === b.dataset.r ? null : b.dataset.r; renderIntel(); }; });
    var it = intelItems().slice(0, 120);
    $('#iList').innerHTML = it.length ? it.map(function (x) {
      return '<div class="iitem"><div class="idate">' + esc(U.date(x.date)) + '</div><div><a class="it" href="' + esc(x.url) + '" target="_blank" rel="noopener">' + esc(x.title) + '</a></div><div class="imeta"><span class="cat cat-' + esc(x.category) + '">' + esc(CATS[x.category] || x.category) + '</span><span>' + esc(x.source || '') + '</span>' + (x.regions || []).map(function (r) { return '<span class="mchip">' + esc(r) + '</span>'; }).join('') + '<span>via ' + esc(x.feed) + '</span></div></div>';
    }).join('') : '<div class="iempty">No items in this window. The feeds run daily; the last attempt is shown under Feed status.</div>';
  }
  function renderSide() {
    var rv = D.review || [];
    $('#rCount').textContent = rv.filter(function (r) { return r.status !== 'closed'; }).length;
    $('#rList').innerHTML = rv.length ? rv.slice(0, 12).map(function (r) { return '<div class="ritem"><b>' + esc(r.title) + '</b><div class="rmeta">' + esc(r.kind) + ' · ' + esc(U.date(r.created)) + (r.url ? ' · <a href="' + esc(r.url) + '" target="_blank" rel="noopener">source</a>' : '') + '</div><div class="small">' + esc(r.action || '') + '</div></div>'; }).join('') :
      '<div class="small">Empty. Curated figures are never changed by feeds; anything that could change a limit, a dataset release or a curated figure is queued here for an analyst.</div>';
    var fd = D.meta.feeds || {};
    $('#fStatus').innerHTML = Object.keys(fd).map(function (k) {
      var f = fd[k], st = f.status || (f.cadence === 'derived' ? 'derived' : 'never run');
      return '<div><span class="st st-' + esc(st) + '">' + esc(st) + (f.stale ? ' · stale' : '') + '</span> <b>' + esc(f.label) + '</b><small>' + esc(f.cadence) + ' · last success ' + esc(f.last_success ? U.stamp(f.last_success) : 'never') + (f.message ? ' · ' + esc(f.message) : '') + '</small></div>';
    }).join('');
  }
  function initIntel() {
    $$('#iWin button').forEach(function (b) { b.onclick = function () { IS.win = +b.dataset.d; $$('#iWin button').forEach(function (x) { x.classList.toggle('on', x === b); }); renderIntel(); }; });
    renderIntel(); renderSide();
    U.layer('cop.json').then(function (cop) {
      var el = document.createElement('div'); el.className = 'card pad';
      el.innerHTML = '<h3>Global COP BLUF ' + U.lbl('CURATED') + '</h3><p class="small">Snapshot ' + esc(cop.meta.asof) + '. Analyst-written; not regenerated by feeds.</p><p style="font-size:13px">' + esc(cop.bluf) + '</p>';
      $('.intel-side').appendChild(el);
    }).catch(function () { });
    $('#refreshLine').innerHTML = 'Data built ' + esc(U.stamp(D.meta.built_at)) + (D.updates_generated_at ? ' · intel feed updated ' + esc(U.stamp(D.updates_generated_at)) : '') + ' · basemap ' + esc(U.tileName()) + '<br>';
  }

  var NET = {
    nodes: [
      ['bw', 'Brackish groundwater (NBGA)', 0, 'nbga_grid'], ['mxaq', 'Mexico aquifers (CONAGUA)', 0, 'mx_aquifers'], ['ggmn', 'Monitoring wells (IGRAC GGMN)', 0, 'ggmn_global'],
      ['pw', 'Produced water (PWDB)', 1, 'pwdb_grid'], ['wells', 'Oil and gas wells (TX, NM, OK, AB, BC, SK)', 1, 'tx_wells_grid'],
      ['swd', 'Injection / disposal wells', 2, 'tx_swd'], ['pot', 'Potabilization plants (MX)', 2, 'mx_plants'], ['wser', 'Wastewater systems (WSER)', 2, 'ca_wser'], ['npdes', 'Major dischargers (NPDES)', 2, 'npdes_majors'],
      ['cws', 'US community water systems', 3, 'sdwa_county'], ['dwa', 'First Nations advisories (CA)', 3, 'ca_dwa'],
      ['dc', 'Data centers (US register)', 4, 'datacenters'], ['eu', 'End users: people served', 4, 'sdwa_county'], ['quake', 'Seismicity (USGS)', 5, 'quakes'], ['drought', 'Drought (USDM)', 5, 'usdm']
    ],
    edges: [
      ['bw', 'dc', 'Brackish groundwater desalinated for cooling (paper scenario)', 'paper', 0], ['pw', 'dc', 'Treated produced water as cooling supply (paper scenario)', 'paper', 1], ['wells', 'pw', 'Wells generate produced water', 'rrc_pw', 1], ['pw', 'swd', 'Most produced water is injected', 'ttu_leeds', 1],
      ['swd', 'quake', 'Disposal linked to induced seismicity in published studies (not attributed here)', 'usgs_quakes', 1], ['bw', 'cws', 'Groundwater supplies many US systems', 'echo_sdwa', 0], ['mxaq', 'pot', 'Aquifers feed potabilization plants', 'conagua', 0],
      ['cws', 'eu', 'Systems deliver to customers', 'echo_sdwa', 0], ['pot', 'eu', 'Plants deliver to customers', 'conagua', 0], ['dwa', 'eu', 'Advisories restrict safe use', 'isc_dwa', 0],
      ['eu', 'wser', 'Customer wastewater is collected', 'wser', 0], ['eu', 'npdes', 'Municipal wastewater (POTW) discharged under NPDES', 'echo_npdes', 0], ['dc', 'cws', 'Data centers compete for municipal supply', 'eesi', 0],
      ['drought', 'cws', 'Drought raises stress on supply', 'usdm', 0], ['drought', 'dc', 'Drought adds siting stress (MODELED)', 'paper', 0], ['ggmn', 'bw', 'Registry of monitoring points', 'igrac', 0]
    ]
  };
  var NET_COL = ['#2397a8', '#38c7ff', '#5b8def', '#4cc39a', '#f2b84b', '#ff7a59'];
  var NET_STAGE = ['Sources', 'Produced water', 'Treatment / disposal', 'Utilities', 'End users and demand', 'Drivers'];
  function recordsFor(layerId) { var l = (D.meta.layers || []).filter(function (x) { return x.id === layerId; })[0]; return l && l.records; }
  function renderGraph() {
    var ch = U.chart('graph'); if (!ch) return;
    var focus = $('#gMode .on').dataset.m === 'pw', keep = focus ? { pw: 1, wells: 1, swd: 1, dc: 1, bw: 1, quake: 1, cws: 1 } : null;
    var nodes = NET.nodes.filter(function (n) { return !keep || keep[n[0]]; }).map(function (n) {
      var rec = (n[3] === 'tx_wells_grid' ? sumRec('_wells_grid') : n[3] === 'tx_swd' ? sumRec('_swd') : recordsFor(n[3])) || 100;
      return { id: n[0], name: n[1], category: n[2], symbolSize: 16 + 7 * Math.log10(Math.max(rec, 10)), value: rec, itemStyle: { color: NET_COL[n[2]], borderColor: '#06101c' }, label: { show: true, color: '#e9eff8', fontSize: 11 } };
    });
    var ids = {}; nodes.forEach(function (n) { ids[n.id] = 1; });
    var links = NET.edges.filter(function (e) { return ids[e[0]] && ids[e[1]]; }).map(function (e) { return { source: e[0], target: e[1], lineStyle: { color: e[4] ? '#38c7ff' : '#4a5d7e', width: e[4] ? 2.2 : 1.3, curveness: 0.12 }, desc: e[2], src: e[3] }; });
    ch.setOption({ tooltip: Object.assign({}, U.TIP, { formatter: function (p) { if (p.dataType === 'edge') return esc(p.data.desc) + '<br><span style="color:#7d8aa3">Source: ' + esc((D.sources[p.data.src] || {}).name || p.data.src) + '</span>'; return '<b>' + esc(p.data.name) + '</b><br>Records in atlas: ' + U.n(p.data.value); } }),
      legend: { data: NET_STAGE.map(function (n) { return { name: n }; }), textStyle: { color: '#a3b2c8' }, bottom: 4 },
      series: [{ type: 'graph', layout: 'force', roam: true, draggable: true, data: nodes, links: links, categories: NET_STAGE.map(function (n, i) { return { name: n, itemStyle: { color: NET_COL[i] } }; }), edgeSymbol: ['none', 'arrow'], edgeSymbolSize: 7, force: { repulsion: 420, edgeLength: [90, 170], gravity: 0.08 }, emphasis: { focus: 'adjacency' }, lineStyle: { opacity: 0.85 } }] }, true);
  }
  function initNetwork() {
    $$('#gMode button').forEach(function (b) { b.onclick = function () { $$('#gMode button').forEach(function (x) { x.classList.toggle('on', x === b); }); renderGraph(); }; });
    $('#gLegend').innerHTML = '<span class="small">Blue edges are the produced-water pathways the atlas focuses on. Hover an edge for the relationship and its source. Drag nodes; scroll to zoom.</span>';
    U.whenVisible($('#graph'), renderGraph);
  }

  function initRegister() {
    var layers = D.meta.layers, sortK = 'title', asc = true, q = '';
    function view() { return layers.filter(function (l) { return !q || (l.title + l.id + l.source + l.label).toLowerCase().indexOf(q) >= 0; }); }
    function render() {
      var v = view().slice().sort(function (a, b) { var x = a[sortK], y = b[sortK]; if (x === y) return 0; if (x === null || x === undefined) return 1; if (y === null || y === undefined) return -1; return (x > y ? 1 : -1) * (asc ? 1 : -1); });
      $('#tCount').textContent = v.length + ' layers';
      $('#table').innerHTML = '<thead><tr>' + [['title', 'Layer'], ['source', 'Source'], ['records', 'Records'], ['asof', 'As of'], ['precision', 'Precision'], ['label', 'Label'], ['size_kb', 'KB']].map(function (c) { return '<th data-k="' + c[0] + '">' + c[1] + '</th>'; }).join('') + '<th>File</th></tr></thead><tbody>' +
        v.map(function (l) { var s = D.sources[l.source]; return '<tr><td>' + esc(l.title) + (l.note ? '<div class="small">' + esc(l.note) + '</div>' : '') + '</td><td>' + (s ? '<a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.name.slice(0, 60)) + '</a>' : esc(l.source)) + '</td><td class="num">' + U.n(l.records) + '</td><td>' + esc(stampOrText(l.asof)) + '</td><td>' + esc(l.precision) + '</td><td>' + U.lbl(l.label) + '</td><td class="num">' + U.n(l.size_kb) + '</td><td><a href="' + esc(l.file) + '" target="_blank" rel="noopener">open</a></td></tr>'; }).join('') + '</tbody>';
      $$('#table th[data-k]').forEach(function (th) { th.style.cursor = 'pointer'; th.onclick = function () { if (sortK === th.dataset.k) asc = !asc; else { sortK = th.dataset.k; asc = true; } render(); }; });
    }
    $('#tSearch').oninput = function () { q = this.value.toLowerCase(); render(); };
    $('#tCsv').onclick = function () { U.download('poseidon_watint_register.csv', U.toCSV(view().map(function (l) { return { id: l.id, title: l.title, source: l.source, records: l.records, asof: l.asof, precision: l.precision, label: l.label, file: l.file }; }), ['id', 'title', 'source', 'records', 'asof', 'precision', 'label', 'file']), 'text/csv'); };
    render();
  }
  function initFindings() {
    var F = D.findings;
    $('#findLead').innerHTML = '<b>Headline:</b> ' + esc(F[0].title) + '. Produced water is a large, salty, regulated stream; whether it can serve data-center cooling is a treatment, logistics and permitting question more than a volume question.';
    $('#findList').innerHTML = F.map(function (f) { return '<li><b>' + esc(f.title) + '</b> ' + U.lbl(f.label.split(';')[0]) + '<br><span>' + esc(f.text) + '</span><div class="small">Sources: ' + f.sources.map(function (s) { return U.srcLink(s); }).join(' · ') + (f.asof ? ' · as of ' + esc(stampOrText(f.asof)) : '') + '</div></li>'; }).join('');
    var R = D.reel_check;
    $('#reelPaper').innerHTML = '<b>Paper:</b> ' + esc(R.paper.citation) + ' <a href="' + esc(R.paper.url) + '" target="_blank" rel="noopener">doi:' + esc(R.paper.doi) + '</a>. ' + esc(R.paper.abstract_finding) + ' ' + esc(R.note);
    $('#reelTable').innerHTML = '<thead><tr><th>Reel claim</th><th>Verdict</th><th>Evidence</th><th>Sources</th></tr></thead><tbody>' + R.claims.map(function (c) {
      var cls = /^(NOT|OVER)/.test(c.verdict) ? 'v-bad' : /^PARTLY/.test(c.verdict) ? 'v-warn' : 'v-ok';
      return '<tr><td>' + esc(c.claim) + '</td><td class="verdict ' + cls + '">' + esc(c.verdict) + '</td><td>' + esc(c.evidence) + '</td><td>' + c.sources.map(function (s) { return U.srcLink(s); }).join('<br>') + '</td></tr>'; }).join('') + '</tbody>';
  }
  var METHOD = [
    'Scope: open, unclassified public data only. Every number is read from the cited source or computed from cited numbers with the formula shown. Where no open source exists the atlas says so and shows nothing (no imputation).',
    'Layers are pre-aggregated by <code>scripts/pipeline.py</code> into <code>data/layers/</code>. Raw downloads (not committed) stay in <code>data/state/raw/</code>. Curated inputs (limits, source registry, COP snapshot, Aqueduct table, reel check) live in <code>data/source/</code> and are never changed by feeds; feed findings that could change them go to <code>data/review.json</code>.',
    'Wells: Texas Railroad Commission GIS well locations (1.4 million records) are binned to 0.1° cells by RRC symbol class. Injection/disposal wells include EOR injection. Per-well produced-water volumes are not published in the layer used.',
    'Produced water chemistry: USGS PWDB v3.0 (113,135 records). TDS medians per basin and 0.25° cell. Coordinates flagged approximate in the source are shown as such.',
    'Water Quality Portal: groundwater wells, results since 2010-01-01, non-detects dropped, units converted to mg/L (nitrate as N), µg/L (arsenic) or ng/L (PFAS). Aggregated by county FIPS and HUC8; exceedance is the share of results above the selected limit. These are monitoring wells, not a statistical sample of drinking water.',
    'Limits: reference values from EPA, Health Canada and NOM-127-SSA1-2021 pages recorded in <code>reference.json</code> with URLs. They are comparison values (some are aesthetic, not health-based), not compliance determinations. PFOA/PFOS values reflect the 2024 EPA MCLs; a compliance-date extension was proposed and not final as of this build.',
    'Siting score (MODELED): score = 100 × (w1·brackish + w2·produced + w3·stress + w4·demand); default weights 0.30/0.30/0.25/0.15, adjustable in the browser. Inspired by the SWUI idea, not the paper\'s metric; the paper\'s full text was not accessed.',
    'Coordinates are WGS 84. MGRS is computed in the browser (UTM zones with the Norway/Svalbard exceptions; polar regions n/a). Precision classes (F, M, G, C, A, E) show how a position was derived, with a nominal circular error.',
    'Basemaps are live tiles: Esri World Imagery, World Topographic, Dark Gray Canvas, and Terrarium elevation tiles for hillshade and 3D. Optional keyed providers are configured in <code>assets/js/config.js</code>.',
    'Live browser feeds: USGS earthquakes (CORS allowed) refresh on load when online. GDACS blocks cross-origin browser requests, so GDACS is refreshed by the scheduled pipeline. GDELT is rate-limited, so headlines come from the pipeline.'
  ];
  var GAPS = [
    'North America wells: Texas (RRC), New Mexico (OCD), Oklahoma (OCC), Alberta (AER ST37), British Columbia (BCER) and Saskatchewan are collected. Not collected: Colorado, North Dakota, Wyoming, Pennsylvania and other US states, Manitoba and the other provinces, and Mexico. Mexico has no open coordinate registry reachable here: the CNH hydrocarbon portal (hidrocarburos.gob.mx) timed out (HTTP 522), and the SENER completed-wells CSVs on datos.gob.mx (2026 development wells only) return Access Denied to automated clients from this network. The IM3 (PNNL) atlas has no scriptable open endpoint here.',
    'Well class counts apply the atlas\'s own grouping of each regulator\'s status codes (mapping is in each layer file note); regulators define "plugged", "shut-in" and "active" differently, so counts are comparable within a jurisdiction, not exactly across them. Alberta and Saskatchewan injection counts include EOR, steam and solvent injection as well as disposal.',
    'Produced-water volumes: only New Mexico (OCD rolling 12-month) and Oklahoma (OCC 2025 Form 1012 workbook) publish per-well injection volumes in the layers used, and neither service states a unit (read here as barrels, ANALYTIC ASSESSMENT). Texas RRC, Alberta, British Columbia and Saskatchewan layers carry no volumes, so disposal-well counts are a proxy there. Produced-water generation by well or operator is not in any open layer used. Treatment-plant intake or capacity for US utilities is not in SDWIS.',
    'Mexico: CONAGUA datos abiertos are reachable only from some networks (TLS/WAF); this build holds a dated local copy and the live refresh degrades to "stale" if blocked. Treatment-plant catalogues have no coordinates, so plants appear as state totals only.',
    'Canada: ISC advisories cover First Nations on-reserve public systems only; provincial and municipal advisories are not aggregated. WSER lists systems that discharge 100 m³/day or more.',
    'Worldwide wells and samples: no complete global dataset exists. IGRAC GGMN is a registry that the open WFS serves point by point (no chemistry values here); UNEP GEMStat has no public bulk API (its portal caps a request at 675 stations); national networks differ in definitions, depth, methods and openness. The atlas shows what is open and treats coverage as a floor.',
    'Data centers: a third-party compiled register with approximate coordinates and no water-use values. Figures like "up to 5 million gallons a day" are upper bounds from secondary sources.',
    'The reel\'s "8 billion gallons a day" figure was checked and could not be supported by primary sources (see Findings).'
  ];
  function initMethod() {
    $('#methodL').innerHTML = '<h3>How the numbers are made</h3><ul class="bul">' + METHOD.map(function (m) { return '<li>' + m + '</li>'; }).join('') + '</ul>';
    $('#precText').textContent = 'Every plotted position carries a class; the detail panel shows it with the nominal circular error (CE). It describes how the coordinate was produced, not a measured accuracy.';
    $('#precTable').innerHTML = '<thead><tr><th>Class</th><th>Meaning</th><th>CE</th></tr></thead><tbody>' + Object.keys(REF.precision).map(function (k) { var p = REF.precision[k]; return '<tr><td><b>' + k + '</b></td><td>' + esc(p.label) + '<div class="small">' + esc(p.desc) + '</div></td><td class="num">' + U.n(p.ce_m) + ' m</td></tr>'; }).join('') + '</tbody>';
    $('#lblTable').innerHTML = '<tbody>' + Object.keys(REF.labels).map(function (k) { return '<tr><td>' + U.lbl(k) + '</td><td>' + esc(REF.labels[k]) + '</td></tr>'; }).join('') + '</tbody>';
    $('#gapList').innerHTML = '<h3>Known gaps and limits</h3><ul class="bul">' + GAPS.map(function (m) { return '<li>' + esc(m) + '</li>'; }).join('') + '</ul>';
  }
  function initSources() {
    $('#srcList').innerHTML = Object.keys(D.sources).map(function (k) { var s = D.sources[k]; return '<a class="src" href="' + esc(s.url || '#') + '" target="_blank" rel="noopener"><b>' + esc(s.name) + '</b><small>' + esc(s.publisher) + '</small><small>' + esc(s.role) + '</small><small>Cadence: ' + esc(s.cadence) + (s.asof ? ' · as of ' + esc(/^\d{4}-\d\d-\d\dT/.test(s.asof) ? U.date(s.asof) : s.asof) : '') + (s.records ? ' · ' + U.n(s.records) + ' records' : '') + '</small></a>'; }).join('');
  }
  function initNav() {
    var links = $$('#nav a'), secs = links.map(function (a) { return $(a.getAttribute('href')); });
    function onScroll() { var y = window.scrollY + 140, cur = 0; secs.forEach(function (s, i) { if (s && s.offsetTop <= y) cur = i; }); links.forEach(function (a, i) { a.classList.toggle('on', i === cur); }); }
    window.addEventListener('scroll', onScroll, { passive: true }); onScroll();
    $('#navToggle').onclick = function () { var o = $('#nav').classList.toggle('open'); this.setAttribute('aria-expanded', o); };
    $$('#nav a').forEach(function (a) { a.onclick = function () { $('#nav').classList.remove('open'); }; });
    var sel = $('#fRegion'); sel.innerHTML = Object.keys(REF.regions).map(function (k) { return '<option value="' + k + '">' + esc(REF.regions[k].label || k) + '</option>'; }).join('');
    sel.value = 'na'; sel.onchange = function () { flyRegion(sel.value); document.getElementById('map').scrollIntoView(); };
    $('#fbToggle').onclick = function () { var o = $('#fbBody').classList.toggle('open'); this.setAttribute('aria-expanded', o); };
  }

  function boot() {
    LAYERS.forEach(function (L) { if (L.on) S.on[L.id] = true; });
    renderKPIs(); renderLayerList(); initNav(); initMap(); initIntel(); initNetwork(); initRegister(); initFindings(); initMethod(); initSources();
    A.ready = true; document.dispatchEvent(new Event('wt-ready'));
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
