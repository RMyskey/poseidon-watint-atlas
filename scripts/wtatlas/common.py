"""Shared helpers: paths, JSON I/O, HTTP with retries, streaming downloads, time, logging."""
import datetime as dt
import gzip
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, 'data')
SRC = os.path.join(DATA, 'source')
STATE = os.path.join(DATA, 'state')
RAW = os.path.join(STATE, 'raw')          # large raw downloads; git-ignored, never deployed
LAYERS = os.path.join(DATA, 'layers')     # pre-aggregated JSON/GeoJSON loaded lazily by the browser

DEFAULT_UA = os.environ.get('WT_USER_AGENT', 'PoseidonNARINT-WATINT-Atlas-Pipeline/1.0 (open-data research prototype; +https://github.com/)')
BROWSER_UA = 'Mozilla/5.0 (X11; Linux x86_64) PoseidonWATINT/1.0'


def log(*a):
    print('[wt]', *a, file=sys.stderr, flush=True)


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t):
    return t.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ') if t else None


def today():
    return now().strftime('%Y-%m-%d')


def parse_iso(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError:
        return None


def load(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path, obj, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(tmp, path)


def sha(s, n=16):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:n]


class HTTPError(Exception):
    pass


def fetch(url, params=None, headers=None, timeout=40, retries=2, backoff=6, ua=None, method='GET', data=None):
    """GET/POST a URL and return bytes. Retries on 429/5xx and network errors."""
    if params:
        url = url + ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
    h = {'User-Agent': ua or DEFAULT_UA, 'Accept-Encoding': 'gzip'}
    h.update(headers or {})
    if isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=h, method=method, data=data)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    body = gzip.decompress(body)
                return body
        except urllib.error.HTTPError as e:
            last = HTTPError('HTTP %s for %s' % (e.code, url.split('?')[0]))
            if e.code not in (429, 500, 502, 503, 504):
                raise last
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = HTTPError('%s for %s' % (e, url.split('?')[0]))
        if attempt < retries:
            time.sleep(backoff * (attempt + 1))
    raise last


def fetch_json(url, **kw):
    return json.loads(fetch(url, **kw).decode('utf-8'))


def download(url, dest, timeout=300, ua=None, params=None, min_bytes=1000):
    """Stream a (possibly large) file to dest atomically. Returns size in bytes."""
    if params:
        url = url + ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={'User-Agent': ua or BROWSER_UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r, open(dest + '.part', 'wb') as f:
            shutil.copyfileobj(r, f, 1 << 20)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        if os.path.exists(dest + '.part'):
            os.remove(dest + '.part')
        raise HTTPError('%s for %s' % (e, url.split('?')[0]))
    size = os.path.getsize(dest + '.part')
    if size < min_bytes:
        os.remove(dest + '.part')
        raise HTTPError('download too small (%d bytes) for %s' % (size, url.split('?')[0]))
    os.replace(dest + '.part', dest)
    return size


def num(v):
    """Parse a float from a messy string; None when not numeric."""
    try:
        f = float(str(v).replace(',', '').strip())
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def r3(x):
    return None if x is None else round(x, 3)


def median(vals):
    v = sorted(vals)
    n = len(v)
    if not n:
        return None
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def pctl(vals, p):
    v = sorted(vals)
    if not v:
        return None
    k = (len(v) - 1) * p
    f = int(k)
    c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)
