"""limits_watch: checks whether sources behind CURATED figures changed. Never edits curated files;
changes become review-queue items (data/review.json) for an analyst to confirm."""
from .common import *

FR = 'https://www.federalregister.gov/api/v1/documents.json'
SB = 'https://www.sciencebase.gov/catalog/item/%s?format=json&fields=title,dateCreated,lastUpdated,provenance'
ITEMS = {'pwdb': '64fa1e71d34ed30c2054ea11', 'nbga': '589365b5e4b0fa1e59b7331e'}


def run(state):
    """state: dict persisted in data/state/watch.json. Returns (review_items, state)."""
    rev = []
    # 1. Federal Register: newest PFAS MCL documents (limits for PFOA/PFOS are CURATED in reference.json)
    try:
        d = fetch_json(FR + '?per_page=5&order=newest&conditions[term]=PFOA+PFOS+maximum+contaminant+level&conditions[agencies][]=environmental-protection-agency', timeout=40, retries=2)
        docs = [(x['document_number'], x['title'], x['publication_date'], x['html_url']) for x in d.get('results', [])]
        seen = set(state.get('fr_seen', []))
        if seen:
            for dn, t, pd, u in docs:
                if dn not in seen:
                    rev.append({'id': 'fr-' + dn, 'kind': 'limit', 'title': 'New Federal Register document on PFOA/PFOS drinking-water limits: ' + t, 'url': u, 'date': pd,
                                'action': 'Read the document and update data/source/reference.json limits (pfoa, pfos) if the MCL or compliance date changed.'})
        state['fr_seen'] = sorted(seen | {x[0] for x in docs})
    except Exception as e:
        rev.append({'id': 'watch-fr-err', 'kind': 'feed', 'title': 'Federal Register watch failed: %s' % str(e)[:120], 'action': 'None needed unless it persists.'})
    # 2. ScienceBase item modification dates for the two USGS databases
    for k, iid in ITEMS.items():
        try:
            d = fetch_json(SB % iid, timeout=40, retries=2)
            lu = (d.get('provenance') or {}).get('lastUpdated') or d.get('lastUpdated')
            prev = state.get('sb_' + k)
            if prev and lu and lu != prev:
                rev.append({'id': 'sb-%s-%s' % (k, lu[:10]), 'kind': 'dataset', 'title': 'USGS ScienceBase item for %s was updated (%s)' % (k.upper(), lu), 'url': 'https://www.sciencebase.gov/catalog/item/' + iid,
                            'action': 'Check for a new release; re-run the %s feed with --force and compare record counts.' % k})
            if lu:
                state['sb_' + k] = lu
        except Exception as e:
            log('watch sciencebase %s: %s' % (k, e))
    state['checked'] = iso(now())
    return rev, state
