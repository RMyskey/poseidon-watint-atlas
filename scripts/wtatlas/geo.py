"""WGS 84 -> MGRS (port of assets/js/geo.js so site and exports agree)."""
import math

D2R = math.pi / 180


def mgrs(lat, lon):
    if lat < -80 or lat > 84:
        return 'n/a (polar)'
    lon = ((lon + 180) % 360 + 360) % 360 - 180
    z = int(math.floor((lon + 180) / 6)) + 1
    if 56 <= lat < 64 and 3 <= lon < 12:
        z = 32
    if 72 <= lat < 84:
        if 0 <= lon < 9: z = 31
        elif 9 <= lon < 21: z = 33
        elif 21 <= lon < 33: z = 35
        elif 33 <= lon < 42: z = 37
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    e2 = f * (2 - f); ep2 = e2 / (1 - e2); e4 = e2 * e2; e6 = e4 * e2
    phi, lam, lam0 = lat * D2R, lon * D2R, ((z - 1) * 6 - 180 + 3) * D2R
    N = a / math.sqrt(1 - e2 * math.sin(phi) ** 2); T = math.tan(phi) ** 2; C = ep2 * math.cos(phi) ** 2; A = math.cos(phi) * (lam - lam0)
    M = a * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
             + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi) - (35 * e6 / 3072) * math.sin(6 * phi))
    E = k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5 / 120) + 500000
    Nn = k0 * (M + N * math.tan(phi) * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * A ** 4 / 24 + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6 / 720))
    if lat < 0:
        Nn += 10000000
    band = 'CDEFGHJKLMNPQRSTUVWXX'[int(math.floor((lat + 80) / 8))]
    col = ['ABCDEFGH', 'JKLMNPQR', 'STUVWXYZ'][(z - 1) % 3][int(math.floor(E / 100000)) - 1]
    row = 'ABCDEFGHJKLMNPQRSTUV'[(int(math.floor(Nn / 100000)) + (5 if z % 2 == 0 else 0)) % 20]
    p5 = lambda v: str(int(math.floor(v % 100000))).zfill(5)
    return '%d%s %s%s %s %s' % (z, band, col, row, p5(E), p5(Nn))


def hav_km(a, b):
    """a, b = (lat, lon)."""
    p1, p2 = a[0] * D2R, b[0] * D2R
    dla, dlo = (b[0] - a[0]) * D2R, (b[1] - a[1]) * D2R
    h = math.sin(dla / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlo / 2) ** 2
    return 2 * 6371.0088 * math.asin(min(1, math.sqrt(h)))
