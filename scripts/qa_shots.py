#!/usr/bin/env python3
"""Headless QA: loads the site from http://localhost:8765, records console errors, saves screenshots.
Usage: python3 scripts/qa_shots.py [base_url]   (serve first: python3 -m http.server 8765)"""
import sys, os, json, time
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'screenshots')
os.makedirs(OUT, exist_ok=True)
errors, warns, failed = [], [], []

with sync_playwright() as p:
    b = p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'])
    pg = b.new_page(viewport={'width': 1500, 'height': 940})
    pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else (warns.append(m.text) if m.type == 'warning' else None))
    pg.on('pageerror', lambda e: errors.append('PAGEERROR ' + str(e)))
    pg.on('requestfailed', lambda r: failed.append(r.url[:140] + ' ' + str(r.failure)))
    pg.goto(BASE, wait_until='load', timeout=90000)
    pg.wait_for_timeout(9000)
    pg.screenshot(path=OUT + '/map.png')
    # open some map layers + zoom to Permian for a richer map shot
    pg.evaluate("""() => { const A = window.WTApp; ['wells','swd','dcs','npdes'].forEach(i => A.setLayer(i, true)); A.flyRegion('permian'); }""")
    pg.wait_for_timeout(9000)
    pg.screenshot(path=OUT + '/map_permian_layers.png')
    # North America overview with every well layer on (new in the multi-jurisdiction build)
    pg.evaluate("""() => { const A = window.WTApp; ['wells','swd','swd_vol'].forEach(i => A.setLayer(i, true)); A.flyRegion('na'); }""")
    pg.wait_for_timeout(12000)
    pg.screenshot(path=OUT + '/map_na_wells.png')
    # force lazy inits then screenshot each section
    pg.evaluate("() => { (window.WTU.lazy || []).forEach(f => f()); }")
    def shot(sel, name, wait=6000):
        pg.evaluate("s => document.querySelector(s).scrollIntoView()", sel)
        pg.wait_for_timeout(wait)
        el = pg.query_selector(sel)
        el.screenshot(path=OUT + '/' + name + '.png')
    shot('#intel', 'intel', 2500)
    shot('#network', 'network', 4000)
    shot('#flow', 'supply_flow', 5000)
    shot('#oilgas', 'na_oil_gas', 12000)
    pg.evaluate("() => { const c = document.querySelector('input[data-d=\"ogMap:swd_vol\"]'); if (c && !c.checked) c.click(); }")
    for reg, name in (('na', 'og_north_america'), ('newmexico', 'og_new_mexico'), ('oklahoma', 'og_oklahoma'), ('alberta', 'og_alberta')):
        pg.evaluate("() => { const b = document.querySelector('#ogPreset button[data-r=\"" + reg + "\"]'); b.click(); }")
        pg.evaluate("() => { const A = window.WTApp; }")
        pg.wait_for_timeout(7000)
        pg.query_selector('#ogMap').screenshot(path=OUT + '/' + name + '.png')
    shot('#samples', 'sample_explorer', 14000)
    shot('#siting', 'data_center_siting', 12000)
    shot('#charts', 'chart_builder', 4000)
    shot('#data', 'data_register', 1500)
    shot('#findings', 'findings', 1500)
    shot('#method', 'method', 1500)
    # mobile
    m = b.new_page(viewport={'width': 400, 'height': 800})
    m.on('console', lambda x: errors.append('[mobile] ' + x.text) if x.type == 'error' else None)
    m.on('pageerror', lambda e: errors.append('[mobile] PAGEERROR ' + str(e)))
    m.goto(BASE, wait_until='load', timeout=90000); m.wait_for_timeout(6000)
    m.screenshot(path=OUT + '/_mobile.png')
    b.close()
res = {'errors': errors, 'warnings': warns[:20], 'failed_requests': failed[:40]}
print(json.dumps(res, indent=1)[:6000])
