"""US data center register (competing demand layer).

Primary: FracTracker Alliance U.S. Data Centers Tracker, as served by the public ArcGIS layer "Data Centers in the United States"
(University of Oregon account, item 41afd711ce9a45609bb8c84c3f44beb8, described as downloaded from FracTracker and updated daily).
Entries are media/analyst compiled; coordinates carry a location_confidence rating. MW, cooling and size are often blank: blanks stay blank."""
import datetime as dt
import json

from .common import LAYERS, fetch_json, iso, log, now, num, save

BASE = 'https://services1.arcgis.com/4yjifSiIG17X0gW4/arcgis/rest/services/Data_Centers/FeatureServer/0'
FIELDS = ['facility_name', 'city', 'state', 'county', 'lat', 'long', 'status', 'location_confidence', 'operator_name', 'tenant', 'mw', 'mw_low', 'mw_high',
          'cooling_source', 'cooling_type', 'facility_size_sqft', 'expected_date_online', 'information_source', 'date_updated']


def mw_value(s):
    """Return (low, high) MW from strings such as '75', '168-240 ', '1400'. None when blank or unparseable."""
    s = (s or '').strip().replace(',', '')
    if not s:
        return None, None
    parts = [num(p) for p in s.replace('–', '-').split('-')]
    parts = [p for p in parts if p is not None]
    if not parts:
        return None, None
    return min(parts), max(parts)


def run():
    total = fetch_json(BASE + '/query', params={'where': '1=1', 'returnCountOnly': 'true', 'f': 'json'}, timeout=60)['count']
    rows, off = [], 0
    while off < total:
        d = fetch_json(BASE + '/query', params={'where': '1=1', 'outFields': ','.join(FIELDS), 'returnGeometry': 'false', 'orderByFields': 'OBJECTID', 'resultOffset': off,
                                                  'resultRecordCount': 1000, 'f': 'json'}, timeout=90, retries=3)
        feats = d.get('features', [])
        if not feats:
            break
        rows += [f['attributes'] for f in feats]
        off += len(feats)
    out, skipped = [], 0
    for a in rows:
        la, lo = num(a.get('lat')), num(a.get('long'))
        if la is None or lo is None or not (15 < la < 72 and -170 < lo < -60):
            skipped += 1
            continue
        lo_mw, hi_mw = mw_value(a.get('mw'))
        upd = a.get('date_updated')
        out.append({'name': (a.get('facility_name') or '').strip(), 'city': (a.get('city') or '').strip(), 'state': (a.get('state') or '').strip(), 'county': (a.get('county') or '').strip(),
                    'lat': round(la, 4), 'lon': round(lo, 4), 'status': a.get('status') or '', 'loc_conf': a.get('location_confidence') or '', 'operator': (a.get('operator_name') or '').strip(),
                    'tenant': (a.get('tenant') or '').strip(), 'mw_low': lo_mw, 'mw_high': hi_mw, 'cooling_source': (a.get('cooling_source') or '').strip(), 'cooling_type': (a.get('cooling_type') or '').strip(),
                    'sqft': num(a.get('facility_size_sqft')), 'online': (a.get('expected_date_online') or '').strip() if isinstance(a.get('expected_date_online'), str) else '',
                    'info_source': a.get('information_source') or '', 'updated': dt.datetime.fromtimestamp(upd / 1000, dt.timezone.utc).strftime('%Y-%m-%d') if upd else ''})
    out.sort(key=lambda r: (r['state'], r['county'], r['name']))
    st = {}
    for r in out:
        st[r['status']] = st.get(r['status'], 0) + 1
    save(LAYERS + '/datacenters.json', {
        'asof': iso(now()), 'source': "FracTracker Alliance U.S. Data Centers Tracker (via University of Oregon ArcGIS feature layer)", 'url': 'https://www.fractracker.org/',
        'layer_url': BASE, 'records': len(out), 'skipped_bad_coords': skipped, 'by_status': st, 'rows': out,
        'note': 'Third-party compiled register (media monitoring and analyst entry). Not independently verified here. Water use is not reported in this dataset; cooling fields are mostly blank.'}, compact=True)
    return {'records': len(out), 'by_status': st, 'with_cooling': sum(1 for r in out if r['cooling_type'] or r['cooling_source']), 'with_mw': sum(1 for r in out if r['mw_low'] is not None)}
