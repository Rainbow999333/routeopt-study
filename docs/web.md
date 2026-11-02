# Static website

## Published release

- Production: https://routeopt-study.pages.dev/
- Immutable deployment: https://7a4155d6.routeopt-study.pages.dev/
- Static asset source: `29ebb2c63f25f8e872fed0da9d861fd08e2ef444`.
- Cloudflare Pages Direct Upload, production branch `main`; only the eight files under `web/` are deployed.
- Verified on 2026-11-03 (Asia/Shanghai), Chromium 154 on the existing free Linux test machine. All 32 browser checks passed: four widths (360/430/1024/1440), four scenarios, NN/2-opt visibility, vehicle selection, playback/pause, zoom/reset, keyboard focus/selection, real downloads and matching bytes, mobile touch, reduced motion, missing-data controls and recovery. Normal execution had no browser runtime/console errors.
- All eight production resources separately returned HTTP 200 and matched the reviewed release byte-for-byte; JavaScript MIME types were checked. Default Python urllib identification received HTTP 403; the explicit `RouteoptReleaseCheck/1.0` client succeeded, as did curl and the browser. No access-control settings were changed.
- Reports: [browser](verification/browser-2026-11-03.json), [public resources](verification/public-http-2026-11-03.json). Screenshots and a 15-second actual-playback MP4 are retained in the separate submission evidence folder, outside the website.

The account owner confirmed on 2026-11-03 that the production site opens and interactions work on their phone over mobile data. This is user-reported acceptance, separate from the automated browser evidence; phone model, browser and carrier were not recorded. It does not establish reachability on every carrier or browser. Personal career report/PPT and contest submission are also separate from this technical release.

Future releases can use `wrangler pages deploy web --project-name routeopt-study --branch main` after the account owner authenticates. Preserve the previous release ZIP and deployment URL for rollback. This project already exists on Pages; no migration or temporary hosting account is needed.

## Repository presentation update (2026-11-03)

The default GitHub and Pages production branch is now main. The repository homepage points to the production website and topics include vehicle-routing, logistics, osrm and openstreetmap. The footer links to the public source. Nine additional live browser checks covered footer visibility/overflow at four widths and an actual GitHub-tab opening; see [footer report](verification/footer-2026-11-03.json). This update changes no experiment data.

## Rebuild

Build directly from the committed verified scenario runs:

```bash
python tools/build_web.py
python tools/check_web_reproducible.py
node --check web/app.js
node --test tests/test_web.mjs
python -m http.server 8765 --bind 127.0.0.1 --directory web
```

Publish only web/ to Cloudflare Pages or ModelScope Static. No runtime framework, external CDN, hosted map, API key, account login, compute instance or online solver is needed for visitors. Browser interaction selects precomputed scenarios; it does not claim to rerun optimization.

The static directory includes reviewed scenarios, road geometry, an OSM background road network and CSV comparisons. All URLs are relative and no SPA route fallback is required. Preserve index.html, app.js, model.mjs, styles.css and data/.

By default the builder reads experiments/chongqing-2026-11-01, which is included in a fresh clone. Re-running algorithms is optional. For a new experiment use a new output directory with run_chongqing.py, then pass that directory explicitly using build_web.py --experiments. A new result may require additional road geometry, which must be checked before publication.

Road data uses ODbL-1.0 with attribution. Review every source field before publishing. Do not deploy the repository root, private local files, wheel/build output or complete experiment directories. Local data has been selected from public OSM road nodes and simulated item demand; no customer data or third-party map credentials.

Browser verification must cover scenario selection, NN/2-opt overlays, vehicle highlight, playback/pause, zoom/reset, downloads, keyboard focus, narrow/mobile/desktop widths, reduced motion and missing data. A terminal test or successful static HTTP response alone does not prove these.

