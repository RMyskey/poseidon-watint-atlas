"""Intel feed: GDELT DOC 2.0 and Google News RSS headline alerts for water, produced water and data-center water topics.

Headlines are machine-matched and NOT analyst-verified. Items are classified by simple keyword rules and tagged with regions/themes."""
import datetime as dt
import email.utils
import html
import json
import re
import time
import xml.etree.ElementTree as ET

from .common import BROWSER_UA, fetch, iso, now, sha

RSS_UA = BROWSER_UA

CATEGORIES = [
    ('produced_water', r'produced water|oilfield (waste ?water|water)|saltwater disposal|\bSWD\b|disposal well|wastewater injection|frac(king)? water|flowback|permian.{0,40}water|water.{0,40}permian|induced seismic'),
    ('data_center', r'data cent(er|re)s?.{0,60}(water|cooling|drought|aquifer)|(water|cooling|aquifer).{0,60}data cent(er|re)s?|\bAI\b.{0,40}water (use|demand|consumption)|hyperscale.{0,40}water'),
    ('contamination', r'PFAS|forever chemicals|lead (pipe|service line)|arsenic|nitrate|boil.water|do not (drink|consume)|water advisory|e\. ?coli|cyanotoxin|algal bloom|contaminat|toxic spill|sewage spill|wastewater (spill|overflow|release)'),
    ('drought', r'drought|water (shortage|restriction|rationing|crisis)|aquifer (decline|depletion)|reservoir levels?|low (river|lake) levels|day zero|water stress'),
    ('infrastructure', r'water (main|treatment|plant|utility|system|infrastructure)|wastewater (plant|treatment|system)|desalination|desalinat|pipeline break|dam failure|levee|pump station|treatment plant|water supply'),
    ('regulatory', r'EPA|drinking water (rule|standard|regulation)|attorney general|TCEQ|Railroad Commission|CONAGUA|water (rights|permit|law)|enforcement|lawsuit|consent decree'),
]
CAT_RE = [(c, re.compile(p, re.I)) for c, p in CATEGORIES]
REGIONS = [('Texas', r'\bTexas\b|Permian|Houston|Dallas|Austin|San Antonio|Midland|Odessa|Longview|Rio Grande Valley|\bTCEQ\b|\bERCOT\b'),
           ('New Mexico', r'New Mexico|Delaware Basin|Carlsbad|Santa Fe'), ('Oklahoma/Kansas', r'Oklahoma|Kansas|Cushing'),
           ('Mexico', r'Mexico|Monterrey|CONAGUA|México|Mexican|Tijuana|Nuevo Le[oó]n'), ('Canada', r'Canada|Canadian|Alberta|Ontario|First Nation|Saskatchewan|British Columbia|Quebec'),
           ('US other', r'\bU\.?S\.?\b|United States|California|Arizona|Colorado River|Michigan|Flint|Jackson, Miss|Florida|Georgia|Ohio|Louisiana|Pennsylvania|New Jersey')]
REG_RE = [(n, re.compile(p, re.I if n != 'US other' else 0)) for n, p in REGIONS]
NOISE = re.compile(r'stock|shares|price target|\bNYSE\b|\bNASDAQ\b|\bETF\b|sponsored|horoscope|recipe|coupon|bottled water brand|water bottle|football|nfl|nba|\bmlb\b', re.I)
GN_QUERIES = [
    '"produced water" Permian', '"saltwater disposal" OR "disposal wells" earthquake Texas OR "New Mexico" OR Oklahoma', '"data center" water use Texas', '"data centers" "water" drought OR aquifer OR cooling',
    'Longview Texas data center water', 'PFAS drinking water EPA', 'boil water notice OR "boil water advisory" Texas', 'drought Texas OR Mexico water reservoirs', 'CONAGUA agua sequía presas',
    'First Nations drinking water advisory Canada', 'desalination brackish OR "produced water" treatment', 'Texas Produced Water Consortium OR "Railroad Commission" produced water',
    'wastewater treatment plant sewage spill OR overflow Texas', 'Rio Grande water treaty Mexico delivery', '"Texas Water Development Board" OR "Texas Water Fund"']
GDELT_TOPICS = [
    '("produced water" OR "saltwater disposal" OR "disposal wells") (Permian OR Texas OR "New Mexico")',
    '("data center" OR "data centers") (water OR cooling OR aquifer OR drought) (Texas OR Arizona OR "United States")',
    '(drought OR "water shortage" OR "water restrictions") (Texas OR Mexico OR "Colorado River" OR Canada)',
    '(PFAS OR "boil water" OR "drinking water advisory" OR "water contamination") (Texas OR "United States" OR Canada)',
    '(desalination OR "water treatment plant" OR "wastewater plant") (Texas OR Mexico OR Canada OR "United States")',
]


def classify(text):
    for c, rx in CAT_RE:
        if rx.search(text):
            return c
    return None


def regions(text):
    return [n for n, rx in REG_RE if rx.search(text)]


def make_item(feed, title, url, date, source, summary=''):
    title = html.unescape(re.sub(r'\s+', ' ', title or '')).strip()
    if not title or not url or NOISE.search(title):
        return None
    text = title + ' ' + html.unescape(re.sub(r'<[^>]+>', ' ', summary or ''))
    cat = classify(text)
    if not cat:
        return None
    return {'id': sha(url), 'feed': feed, 'date': iso(date) if date else None, 'title': title, 'url': url, 'source': source, 'category': cat, 'regions': regions(text)}


def parse_rss(raw):
    root = ET.fromstring(raw)
    for it in root.iter('item'):
        g = lambda tag: (it.findtext(tag) or '').strip()
        src = it.find('source')
        d = None
        if g('pubDate'):
            try:
                d = email.utils.parsedate_to_datetime(g('pubDate'))
                if d.tzinfo is None:
                    d = d.replace(tzinfo=dt.timezone.utc)
            except (TypeError, ValueError):
                d = None
        yield {'title': g('title'), 'link': g('link'), 'date': d, 'desc': g('description'), 'source': (src.text.strip() if src is not None and src.text else '')}


def gnews(when='2d', delay=2.0):
    items, errors, n = [], [], 0
    for q in GN_QUERIES:
        try:
            raw = fetch('https://news.google.com/rss/search', params={'q': q + ' when:' + when, 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'}, timeout=30, retries=1, ua=RSS_UA)
            for r in parse_rss(raw):
                title = re.sub(r'\s+-\s+[^-]+$', '', r['title']) if r['source'] else r['title']
                it = make_item('gnews', title, r['link'], r['date'], r['source'] or 'Google News', r['desc'])
                if it:
                    items.append(it)
            n += 1
        except Exception as e:  # noqa: BLE001
            errors.append(str(e)[:120])
        time.sleep(delay)
    return items, n, errors


def gdelt(timespan='2d', delay=12.0):
    items, errors, n = [], [], 0
    for i, q in enumerate(GDELT_TOPICS):
        if i:
            time.sleep(delay)
        try:
            raw = fetch('https://api.gdeltproject.org/api/v2/doc/doc', params={'query': q + ' sourcelang:english', 'mode': 'artlist', 'format': 'json', 'maxrecords': 100, 'timespan': timespan, 'sort': 'datedesc'},
                        timeout=45, retries=2, backoff=20, ua=RSS_UA)
            txt = raw.decode('utf-8', 'replace').strip()
            if not txt.startswith('{'):
                errors.append(txt[:100])
                continue
            for a in json.loads(txt).get('articles', []) or []:
                d = None
                try:
                    d = dt.datetime.strptime(a.get('seendate', ''), '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
                except ValueError:
                    pass
                it = make_item('gdelt', a.get('title'), a.get('url'), d, a.get('domain'))
                if it:
                    items.append(it)
            n += 1
        except Exception as e:  # noqa: BLE001
            errors.append(str(e)[:120])
    return items, n, errors
