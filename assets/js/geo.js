/*  Poseidon WATINT Atlas: geodesy helpers (WGS 84). No dependencies. */
(function (G) {
  'use strict';
  var D2R = Math.PI / 180, R = 6371.0088;
  function havKm(a, b) { // a,b = [lon,lat]
    var dLa = (b[1] - a[1]) * D2R, dLo = (b[0] - a[0]) * D2R;
    var h = Math.sin(dLa / 2) * Math.sin(dLa / 2) + Math.cos(a[1] * D2R) * Math.cos(b[1] * D2R) * Math.sin(dLo / 2) * Math.sin(dLo / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }
  function bearing(a, b) {
    var p1 = a[1] * D2R, p2 = b[1] * D2R, dl = (b[0] - a[0]) * D2R;
    var y = Math.sin(dl) * Math.cos(p2), x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
    return (Math.atan2(y, x) / D2R + 360) % 360;
  }
  function gcPath(a, b, n) { // great-circle path, longitudes unwrapped so lines never jump the antimeridian
    var p1 = a[1] * D2R, l1 = a[0] * D2R, p2 = b[1] * D2R, l2 = b[0] * D2R;
    var d = 2 * Math.asin(Math.sqrt(Math.pow(Math.sin((p2 - p1) / 2), 2) + Math.cos(p1) * Math.cos(p2) * Math.pow(Math.sin((l2 - l1) / 2), 2)));
    if (!d) return [a, b];
    var out = [], prev = null;
    for (var i = 0; i <= n; i++) {
      var f = i / n, A = Math.sin((1 - f) * d) / Math.sin(d), B = Math.sin(f * d) / Math.sin(d);
      var x = A * Math.cos(p1) * Math.cos(l1) + B * Math.cos(p2) * Math.cos(l2);
      var y = A * Math.cos(p1) * Math.sin(l1) + B * Math.cos(p2) * Math.sin(l2);
      var z = A * Math.sin(p1) + B * Math.sin(p2);
      var lon = Math.atan2(y, x) / D2R, lat = Math.atan2(z, Math.sqrt(x * x + y * y)) / D2R;
      if (prev !== null) { while (lon - prev > 180) lon -= 360; while (lon - prev < -180) lon += 360; }
      prev = lon; out.push([lon, lat]);
    }
    return out;
  }
  function circle(lon, lat, m, n) { // geodesic circle polygon ring
    n = n || 64; var out = [], dr = m / 1000 / R, p1 = lat * D2R, l1 = lon * D2R;
    for (var i = 0; i <= n; i++) {
      var t = (i / n) * 2 * Math.PI;
      var p2 = Math.asin(Math.sin(p1) * Math.cos(dr) + Math.cos(p1) * Math.sin(dr) * Math.cos(t));
      var l2 = l1 + Math.atan2(Math.sin(t) * Math.sin(dr) * Math.cos(p1), Math.cos(dr) - Math.sin(p1) * Math.sin(p2));
      out.push([l2 / D2R, p2 / D2R]);
    }
    return out;
  }
  function mgrs(lat, lon) {
    if (lat < -80 || lat > 84) return 'n/a (polar)';
    lon = ((lon + 180) % 360 + 360) % 360 - 180;
    var z = Math.floor((lon + 180) / 6) + 1;
    if (lat >= 56 && lat < 64 && lon >= 3 && lon < 12) z = 32;
    if (lat >= 72 && lat < 84) { if (lon >= 0 && lon < 9) z = 31; else if (lon >= 9 && lon < 21) z = 33; else if (lon >= 21 && lon < 33) z = 35; else if (lon >= 33 && lon < 42) z = 37; }
    var a = 6378137, f = 1 / 298.257223563, k0 = 0.9996, e2 = f * (2 - f), ep2 = e2 / (1 - e2), e4 = e2 * e2, e6 = e4 * e2;
    var phi = lat * D2R, lam = lon * D2R, lam0 = ((z - 1) * 6 - 180 + 3) * D2R;
    var N = a / Math.sqrt(1 - e2 * Math.pow(Math.sin(phi), 2)), T = Math.pow(Math.tan(phi), 2), C = ep2 * Math.pow(Math.cos(phi), 2), A = Math.cos(phi) * (lam - lam0);
    var M = a * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * Math.sin(2 * phi) + (15 * e4 / 256 + 45 * e6 / 1024) * Math.sin(4 * phi) - (35 * e6 / 3072) * Math.sin(6 * phi));
    var E = k0 * N * (A + (1 - T + C) * Math.pow(A, 3) / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * Math.pow(A, 5) / 120) + 500000;
    var Nn = k0 * (M + N * Math.tan(phi) * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * Math.pow(A, 4) / 24 + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * Math.pow(A, 6) / 720));
    if (lat < 0) Nn += 10000000;
    var band = 'CDEFGHJKLMNPQRSTUVWXX'[Math.floor((lat + 80) / 8)];
    var col = ['ABCDEFGH', 'JKLMNPQR', 'STUVWXYZ'][(z - 1) % 3][Math.floor(E / 100000) - 1];
    var row = 'ABCDEFGHJKLMNPQRSTUV'[(Math.floor(Nn / 100000) + (z % 2 === 0 ? 5 : 0)) % 20];
    var p5 = function (v) { return String(Math.floor(v % 100000)).padStart(5, '0'); };
    return z + band + ' ' + col + row + ' ' + p5(E) + ' ' + p5(Nn);
  }
  function fmtDD(la, lo, d) { return Math.abs(la).toFixed(d) + '° ' + (la >= 0 ? 'N' : 'S') + ', ' + Math.abs(lo).toFixed(d) + '° ' + (lo >= 0 ? 'E' : 'W'); }
  function dms(v, pos, neg) {
    var a = Math.abs(v), d = Math.floor(a), mf = (a - d) * 60, m = Math.floor(mf), s = (mf - m) * 60;
    if (s >= 59.95) { s = 0; m += 1; } if (m >= 60) { m = 0; d += 1; }
    return d + '°' + String(m).padStart(2, '0') + '′' + s.toFixed(1).padStart(4, '0') + '″' + (v >= 0 ? pos : neg);
  }
  function fmtDMS(la, lo) { return dms(la, 'N', 'S') + ' ' + dms(lo, 'E', 'W'); }
  G.WTGeo = { havKm: havKm, bearing: bearing, gcPath: gcPath, circle: circle, mgrs: mgrs, fmtDD: fmtDD, fmtDMS: fmtDMS };
})(window);
