/* Poseidon NARINT WATINT atlas: shared helpers, tile config, map factory. */
(function (W) {
  'use strict';
  var D = W.WT, G = W.WTGeo;
  var U = {};
  U.D = D; U.G = G; U.REF = D.ref;
  U.$ = function (s, r) { return (r || document).querySelector(s); };
  U.$$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  U.esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  U.n = function (v, d) { if (v === null || v === undefined || isNaN(v)) return 'n/a'; return Number(v).toLocaleString('en-US', { maximumFractionDigits: d === undefined ? 0 : d }); };
  U.sig = function (v) { if (v === null || v === undefined || isNaN(v)) return 'n/a'; var a = Math.abs(v); return a >= 100 ? U.n(v, 0) : a >= 10 ? U.n(v, 1) : a >= 1 ? U.n(v, 2) : U.n(v, 3); };
  U.date = function (s) { var t = Date.parse(s || ''); return isNaN(t) ? (s || 'n/a') : new Date(t).toISOString().slice(0, 10); };
  U.stamp = function (s) { var t = Date.parse(s || ''); return isNaN(t) ? (s || 'never') : new Date(t).toISOString().replace('T', ' ').slice(0, 16) + ' UTC'; };
  U.toast = function (t) { var el = U.$('#toast'); el.textContent = t; el.hidden = false; clearTimeout(U.toast._t); U.toast._t = setTimeout(function () { el.hidden = true; }, 2400); };
  U.lbl = function (l) { if (!l) return ''; var k = String(l).split(' ')[0].replace(/[^A-Z]/g, ''); return '<span class="lbl ' + U.esc(k) + '">' + U.esc(l) + '</span>'; };
  U.csvCell = function (v) { v = v === null || v === undefined ? '' : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
  U.toCSV = function (rows, cols) { return cols.join(',') + '\n' + rows.map(function (r) { return cols.map(function (c) { return U.csvCell(r[c]); }).join(','); }).join('\n'); };
  U.download = function (name, text, type) {
    var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: type || 'text/plain' })); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  };
  U.src = function (id) { return D.sources[id]; };
  U.srcLink = function (id) { var s = D.sources[id]; return s ? '<a href="' + U.esc(s.url) + '" target="_blank" rel="noopener">' + U.esc(s.name) + '</a>' : U.esc(id); };
  U.asofOf = function (layerId) { var l = (D.meta.layers || []).filter(function (x) { return x.id === layerId; })[0]; return l ? l.asof : null; };

  /* ---- JSON loader with cache (data/layers/*.json are fetched lazily) ---- */
  var cache = {};
  U.json = function (path) {
    if (!cache[path]) {
      cache[path] = fetch(path).then(function (r) { if (!r.ok) throw new Error(path + ' HTTP ' + r.status); return r.json(); })
        .catch(function (e) { delete cache[path]; throw e; });
    }
    return cache[path];
  };
  U.layer = function (name) { return U.json('data/layers/' + name); };

  /* ---- colour helpers ---- */
  U.COL = { cyan: '#38c7ff', blue: '#5b8def', gold: '#f2b84b', warn: '#ffb547', bad: '#ff5c6c', ok: '#3ddc97', purple: '#b06cff', teal: '#2ec4b6', grey: '#7d8aa3' };
  U.SEQ = ['#16365e', '#1f6390', '#2397a8', '#4cc39a', '#b6e37a', '#fff27a'];
  U.HOT = ['#2b1a4f', '#6a2c91', '#c0398b', '#f0643e', '#ffb547', '#fff3a8'];
  U.stepExpr = function (prop, breaks, cols) { var e = ['step', ['coalesce', ['get', prop], -1e9], cols[0]]; for (var i = 0; i < breaks.length; i++) { e.push(breaks[i]); e.push(cols[i + 1]); } return e; };
  U.stepColor = function (v, breaks, cols) { var i = 0; while (i < breaks.length && v >= breaks[i]) i++; return cols[i]; };
  U.legendSteps = function (title, breaks, cols, fmt, label) {
    var h = '<div class="lg-t">' + U.esc(title) + (label ? ' ' + U.lbl(label) : '') + '</div>';
    for (var i = 0; i < cols.length; i++) {
      var t = i === 0 ? '< ' + fmt(breaks[0]) : i === cols.length - 1 ? '≥ ' + fmt(breaks[breaks.length - 1]) : fmt(breaks[i - 1]) + ' to < ' + fmt(breaks[i]);
      h += '<div class="lg-row"><span class="lg-sw" style="background:' + cols[i] + ';border-radius:3px"></span><span>' + U.esc(t) + '</span></div>';
    }
    return h;
  };
  U.fc = function (f) { return { type: 'FeatureCollection', features: f || [] }; };
  U.pt = function (lon, lat, props) { return { type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties: props || {} }; };

  /* ---- tile providers (keyless Esri by default; optional keys in config.js) ---- */
  var ATTR = {
    sat: 'Imagery © <a href="https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9" target="_blank" rel="noopener">Esri</a>, Maxar, Earthstar Geographics, and the GIS User Community',
    ref: 'Reference © Esri',
    topo: 'Topo © <a href="https://www.arcgis.com/home/item.html?id=7dc6cea0b1764a1f9af2e679f642f0f5" target="_blank" rel="noopener">Esri</a>, HERE, Garmin, FAO, NOAA, USGS, © OpenStreetMap contributors, and the GIS User Community',
    dark: 'Dark Gray Canvas © <a href="https://www.arcgis.com/home/item.html?id=358ec1e175ea41c3bf5c68f0da11ae2b" target="_blank" rel="noopener">Esri</a>, HERE, Garmin, © OpenStreetMap contributors, and the GIS User Community',
    dem: 'Elevation: <a href="https://github.com/tilezen/joerd/blob/master/docs/attribution.md" target="_blank" rel="noopener">Tilezen Terrarium</a> (SRTM, GMTED, ETOPO1 et al.)'
  };
  function rasterSrc(tiles, attr, maxz, ts) { return { type: 'raster', tiles: tiles, tileSize: ts || 256, maxzoom: maxz, attribution: attr }; }
  function glyphURL() {
    if (location.protocol === 'file:') return 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf';
    return location.href.replace(/[#?].*$/, '').replace(/[^/]*$/, '') + 'assets/fonts/{fontstack}/{range}.pbf';
  }
  function tileConfig() {
    var c = (W.WT_CONFIG && W.WT_CONFIG.tiles) || {};
    var terrarium = { type: 'raster-dem', tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'], encoding: 'terrarium', tileSize: 256, maxzoom: 15, attribution: ATTR.dem };
    if (c.provider === 'maptiler' && c.maptilerKey) {
      var k = encodeURIComponent(c.maptilerKey);
      var MA = '<a href="https://www.maptiler.com/copyright/" target="_blank" rel="noopener">© MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors</a>';
      return { name: 'MapTiler',
        dark: rasterSrc(['https://api.maptiler.com/maps/dataviz-dark/256/{z}/{x}/{y}.png?key=' + k], MA, 20), darkref: null,
        sat: rasterSrc(['https://api.maptiler.com/tiles/satellite-v2/{z}/{x}/{y}.jpg?key=' + k], MA, 20, 512), ref: null,
        topo: rasterSrc(['https://api.maptiler.com/maps/topo-v2/256/{z}/{x}/{y}.png?key=' + k], MA, 20),
        dem: { type: 'raster-dem', tiles: ['https://api.maptiler.com/tiles/terrain-rgb-v2/{z}/{x}/{y}.webp?key=' + k], encoding: 'mapbox', tileSize: 512, maxzoom: 14, attribution: MA } };
    }
    var keyed = c.provider === 'esri-key' && c.esriApiKey;
    var esri = function (svc) { return keyed ? ['https://ibasemaps-api.arcgis.com/arcgis/rest/services/' + svc + '/MapServer/tile/{z}/{y}/{x}?token=' + encodeURIComponent(c.esriApiKey)] : ['https://server.arcgisonline.com/ArcGIS/rest/services/' + svc + '/MapServer/tile/{z}/{y}/{x}']; };
    return { name: keyed ? 'Esri (API key)' : 'Esri (keyless)',
      dark: rasterSrc(esri('Canvas/World_Dark_Gray_Base'), ATTR.dark, 16), darkref: rasterSrc(esri('Canvas/World_Dark_Gray_Reference'), ATTR.dark, 16),
      sat: rasterSrc(esri('World_Imagery'), ATTR.sat, 19), ref: rasterSrc(esri('Reference/World_Boundaries_and_Places'), ATTR.ref, 19),
      topo: rasterSrc(esri('World_Topo_Map'), ATTR.topo, 19), dem: terrarium };
  }
  U.tileName = function () { return tileConfig().name; };

  /* Base style: dark/sat/topo rasters, optional hillshade, reference labels. Callers push their own sources/layers. */
  U.baseStyle = function () {
    var TC = tileConfig();
    var s = { version: 8, glyphs: glyphURL(), sources: { dark: TC.dark, sat: TC.sat, topo: TC.topo, dem: TC.dem, demhs: JSON.parse(JSON.stringify(TC.dem)) },
      layers: [
        { id: 'bg', type: 'background', paint: { 'background-color': '#060b14' } },
        { id: 'base-dark', type: 'raster', source: 'dark', paint: { 'raster-brightness-max': 0.7, 'raster-saturation': -0.15, 'raster-contrast': 0.12 } },
        { id: 'base-sat', type: 'raster', source: 'sat', layout: { visibility: 'none' } },
        { id: 'base-topo', type: 'raster', source: 'topo', layout: { visibility: 'none' } },
        { id: 'hill', type: 'hillshade', source: 'demhs', layout: { visibility: 'none' }, paint: { 'hillshade-exaggeration': 0.55, 'hillshade-shadow-color': '#000000', 'hillshade-highlight-color': '#9fb6d8' } },
        { id: 'ref', type: 'raster', source: 'ref', layout: { visibility: 'none' } },
        { id: 'darkref', type: 'raster', source: 'darkref', paint: { 'raster-opacity': 0.85 } }
      ] };
    ['ref', 'darkref'].forEach(function (k) { if (TC[k]) s.sources[k] = TC[k]; else s.layers = s.layers.filter(function (l) { return l.id !== k; }); });
    return s;
  };
  U.setBase = function (map, b, ref) {
    ['dark', 'sat', 'topo'].forEach(function (k) { if (map.getLayer('base-' + k)) map.setLayoutProperty('base-' + k, 'visibility', k === b ? 'visible' : 'none'); });
    if (map.getLayer('darkref')) map.setLayoutProperty('darkref', 'visibility', b === 'dark' && ref ? 'visible' : 'none');
    if (map.getLayer('ref')) map.setLayoutProperty('ref', 'visibility', b !== 'dark' && ref ? 'visible' : 'none');
  };
  U.setVis = function (map, id, on) { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'); };

  /* Map factory used by the dashboards. opts: {id, center, zoom, style:{sources,layers}, base} */
  U.mkMap = function (opts) {
    if (!W.maplibregl) { U.$('#' + opts.id).innerHTML = '<p style="padding:40px">Map library failed to load.</p>'; return null; }
    var st = U.baseStyle();
    (opts.layers || []).forEach(function (l) { st.layers.push(l); });
    Object.keys(opts.sources || {}).forEach(function (k) { st.sources[k] = opts.sources[k]; });
    var map = new maplibregl.Map({ container: opts.id, style: st, center: opts.center, zoom: opts.zoom, attributionControl: { compact: true }, fadeDuration: 100, maxPitch: 60 });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-right');
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric', maxWidth: 110 }), 'bottom-right');
    if (opts.readout) map.on('mousemove', function (e) { U.readout(map, opts.readout, e.lngLat); });
    map.on('error', function (e) { if (e && e.error && !/tile|Failed to fetch|AJAXError|NetworkError|Load failed/i.test(String(e.error.message || e.error))) console.warn('map', e.error); });
    U.setBase(map, opts.base || 'dark', true);
    return map;
  };
  U.scaleDen = function (lat, z) { return Math.round(40075016.686 * Math.cos(lat * Math.PI / 180) / (512 * Math.pow(2, z)) / 0.000264583); };
  U.readout = function (map, id, ll, tag) {
    var lat = ll.lat, lon = ((ll.lng + 180) % 360 + 360) % 360 - 180, z = map.getZoom();
    U.$(id).textContent = (tag ? tag + ' ' : '') + lat.toFixed(5) + ', ' + lon.toFixed(5) + '  |  MGRS ' + G.mgrs(lat, lon) + '  |  z ' + z.toFixed(1) + '  |  ≈1:' + U.scaleDen(lat, z).toLocaleString();
  };
  /* Add a GeoJSON source + layers once (or update data). */
  U.setData = function (map, id, data) { var s = map.getSource(id); if (s) s.setData(data); else map.addSource(id, { type: 'geojson', data: data }); };
  /* Lazy init when a section scrolls into view. */
  U.whenVisible = function (el, fn) {
    var done = false;
    function go() { if (done) return; done = true; fn(); }
    if (!('IntersectionObserver' in W)) return go();
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { io.disconnect(); go(); } }); }, { rootMargin: '300px' });
    io.observe(el);
    U.lazy = U.lazy || []; U.lazy.push(go);
  };

  /* ---- ECharts ---- */
  var charts = {};
  U.chart = function (id) {
    var el = U.$('#' + id);
    if (!el || !W.echarts) return null;
    if (charts[id]) { if (charts[id].getDom() !== el) { charts[id].dispose(); charts[id] = null; } else return charts[id]; }
    charts[id] = echarts.init(el, null, { renderer: 'canvas' });
    return charts[id];
  };
  U.resizeAll = function () { Object.keys(charts).forEach(function (k) { try { charts[k].resize(); } catch (e) { /* disposed */ } }); };
  W.addEventListener('resize', U.resizeAll);
  U.AX = { axisLine: { lineStyle: { color: '#33445f' } }, axisLabel: { color: '#a3b2c8' }, splitLine: { lineStyle: { color: '#1a2638' } }, nameTextStyle: { color: '#a3b2c8' } };
  U.TIP = { backgroundColor: 'rgba(8,13,22,.95)', borderColor: '#263650', textStyle: { color: '#e9eff8', fontSize: 12 } };

  /* ---- limits ---- */
  U.limit = function (param, basis) { var p = D.ref.limits.parameters[param]; return p ? p[basis] : null; };
  W.WTU = U;
})(window);
