# Poseidon NARINT / WATINT Water Atlas

Concept prototype: a standalone, GitHub-Pages-ready static atlas of open, unclassified water, produced-water, wastewater, supply-chain and data-center-siting data for North America with a global COP layer. It mirrors the structure of the Millennium KI Strategic Minerals Atlas (same SPA sections, pipeline contract, review queue and labels).

> Poseidon NARINT concept prototype: open, unclassified public data only. Not an official product of the Department of War, USACE, or the Army Geospatial Center.

No private, controlled or classified data is used. Every figure carries a source and an as-of date. Nothing is invented: where no open dataset exists the site says so (see Method > Gaps).

## Sections

Map, Intel feed, Network, Supply flow, Oil & gas, Sample explorer, Data-center siting, Chart builder, Data register, Findings, Method, Sources, About (one page, hash navigation).

| Required analytic | Where |
|---|---|
| Global WATINT COP layer (country threat index, news clusters, GDACS, USDM, live USGS quakes) | Map |
| NA oil & gas wells density, produced water, Class II / SWD, induced seismicity | Oil & gas, Map |
| Municipal supply chains | Supply flow, Map (SDWIS, WSER, ISC advisories, CONAGUA) |
| Sewage / wastewater | Map layers: NPDES majors, ECCC WSER, Mexico PTAR (table only; no coordinates published) |
| Wells + water samples vs EPA / Health Canada / NOM-127 | Sample explorer (WQP aggregated by county and HUC8; CONAGUA RNMCA sites) |
| Worldwide wells / samples | Sample explorer (IGRAC GGMN registry + documentation that no complete global dataset exists) |
| Data-center water siting (MODELED, SWUI-inspired) | Siting, with Longview TX callout and full method |

## Run locally

```
python3 -m http.server 8765      # then open http://localhost:8765/
pip install -r scripts/requirements.txt   # pyshp, only for the pipeline
python3 scripts/pipeline.py               # run feeds that are due, rebuild outputs
python3 scripts/pipeline.py --force       # run every feed now
python3 scripts/pipeline.py --only gdacs,usdm
python3 scripts/pipeline.py --build-only  # no network: regenerate meta/sources/flow/findings/bundle
python3 scripts/qa_shots.py               # headless Chromium: console errors + screenshots/
```

MapLibre GL 5.15.0 and ECharts 5.6.0 are vendored (`assets/vendor`). There is no build step.

## Layout

```
index.html, assets/{css,js,vendor,fonts,img}
assets/js/config.js      tile provider config (keyless Esri by default)
assets/js/data.js        generated small bundle (window.WT)
data/source/             CURATED inputs: reference.json (limits, labels, precision), sources.json,
                         reel_check.json, cop_snapshot.json, supply figures. Feeds never edit these.
data/layers/             generated map/chart layers (GeoJSON/JSON)
data/{meta,sources,flow,findings,updates,review}.json   generated
data/state/              pipeline state (raw/ and wqp_cache/ are git-ignored; watch.json is kept)
scripts/pipeline.py      orchestrator; scripts/wtatlas/*  one module per feed family
.github/workflows/       pages.yml (deploy) and refresh-data.yml (daily cron, then deploy)
```

## Feeds

| Feed | Cadence | Source |
|---|---|---|
| gdacs, quakes, gdelt, gnews | daily | GDACS, USGS FDSN, GDELT DOC 2.0, Google News RSS |
| usdm, datacenters, isc_dwa, limits_watch | weekly | US Drought Monitor, FracTracker data-center register, ISC advisories, Federal Register + ScienceBase release watch |
| rrc, echo_sdwa, echo_npdes, wqp, igrac, conagua, wser | monthly | Texas RRC ArcGIS REST, EPA ECHO (SDWIS, ICIS-NPDES), Water Quality Portal, IGRAC GGIS WFS, CONAGUA, ECCC WSER |
| pwdb, nbga, boundaries | annual | USGS PWDB v3.0 (10.5066/P9DSRCZJ), USGS NBGA (10.5066/F72F7KK1), Census cartographic boundaries |
| siting | derived | Texas data-center siting model, rebuilt when its inputs refresh |

`data/meta.json` records `last_attempt`, `last_success`, record counts, status (`ok` / `stale` / `failed`) per feed. A failed feed keeps its previous layer and is marked `stale`; the site shows the status on the Intel page. GDACS sends no CORS header so it is pipeline-only; USGS quakes are fetched live in the browser with a snapshot fallback.

## Rules

1. Real open citable data only; never invent a number. Source and as-of on every figure.
2. Labels: OBSERVED (source value), CURATED (analyst snapshot), MODELED (atlas formula), ANALYTIC ASSESSMENT (atlas arithmetic on cited figures).
3. Feeds never overwrite curated figures. Anything that would change a limit, a dataset release or a curated value goes to `data/review.json`, shown as the Review queue on the Intel page.
4. Coordinates are WGS 84 with MGRS. Precision classes: F facility, M monitoring site, G grid cell, C county/HUC8/state, A approximate, E event. The class is shown on every detail panel.
5. Limits are reference values from the agency pages (EPA NPDWR, Health Canada GCDWQ, NOM-127-SSA1-2021), not compliance determinations.

## Go live

1. Push to a GitHub repo, set Settings > Pages > Source: GitHub Actions.
2. `pages.yml` deploys on push to main; `refresh-data.yml` runs daily (06:00 UTC) and commits data changes then redeploys. The first run executes every heavy feed (timeout 180 min).
3. Optional keyed basemaps: repository secrets `MAPTILER_KEY` or `ESRI_API_KEY` are written to the deployed `config.js` only. Optional secret `WT_USER_AGENT` sets a contact string for polite fetching. Keys never enter git.

## Reel check (verified against primary sources)

The reel's "8 billion gallons per day" Permian produced-water figure is not supported: Texas Tech/TAWC (2025) gives about 20 million bbl/day (0.84 billion gal/day) and B3 Insight about 20.7 million bpd for 2025; the Railroad Commission gives about 24 million bbl/day for all of Texas (1.0 billion gal/day). 8 billion gal/day would be about 190 million bbl/day, about 10 times too high. The reel's own "about 1,200 Olympic pools" matches 0.84 billion gal/day, not 8. The paper: Katakam, Arzumanyan, Lin, Bahadur, "System-scale design and analysis of desalination systems for meeting water needs of data centers", Water Research 308, 126748, doi:10.1016/j.watres.2026.126748 (online 2026-08-17); abstract and press release only, full text not accessed. Full table: Findings page and `data/source/reel_check.json`.

## Known limitations

- Wells layers cover Texas only (RRC). New Mexico, Oklahoma, Canada and Mexico well registries are not scriptable open feeds in this build.
- RRC does not publish per-well produced-water volumes; disposal density is a proxy.
- WQP aggregates use the site median since 2010; monitoring sites are not a random sample. Percent-above-limit is precomputed against the EPA value only.
- GGMN is a registry of points (counts of level and quality series), not chemistry. UNEP GEMStat has no public bulk API (portal limit 675 stations) and is not ingested.
- Mexico PTAR / potabilization plants have no published coordinates; shown in tables only.
- The siting score is MODELED and is not the SWUI of the cited paper (full text not accessed); it is a screening aid, not a permitting or cost assessment.
- The Intel COP country index and BLUF are a CURATED snapshot (dated), not regenerated by feeds.
