# Static website

## Current production release (2026-11-03)

- Production: https://routeopt-study.pages.dev/
- Immutable deployment: https://29bcfbb1.routeopt-study.pages.dev/
- Static asset source: `e3377e9aa4e77106fdb9fec6a80f3c97d2351fc7`, CI [41500867966](https://github.com/Rainbow999333/routeopt-study/actions/runs/41500867966): all five jobs successful (Windows/Linux, Python3.11/3.13 and website).
- Cloudflare Pages Direct Upload, production branch `main`; only the nine reviewed files under `web/` are deployed. The default GitHub branch is `main`, homepage is the production URL, topics include vehicle-routing/logistics/osrm/openstreetmap, and the footer links to source.
- Four precomputed simulated-demand road scenarios remain unchanged. Time and variable-cost interpretation is separate from the 21-parcel historical-task counterfactual study. No visitor input is sent to a server, and no online solver is claimed.

The final candidate passed the complete [32-check original route regression](verification/history-route-regression-2026-11-03.json) and [24 historical checks](verification/history-candidate-2026-11-03.json). After production deployment, Chromium154 on the existing free Linux test machine passed [24 historical checks](verification/history-public-2026-11-03.json) and [35 time/cost checks](verification/history-decision-public-2026-11-03.json), covering 360/430/1024/1440 widths, disclosures, actual downloads, unusual rate inputs, independent missing-data failures and recovery. Normal execution had no runtime/console errors. Mobile/desktop screenshots were visually reviewed.

All [nine public resources](verification/history-http-2026-11-03.json) returned HTTP200, matched the reviewed source byte-for-byte, and had appropriate JavaScript MIME types. One local connection ended with a TLS EOF; a single retry completed all nine. No TLS verification or access control was disabled. An earlier release required the explicit `RouteoptReleaseCheck/1.0` user agent because the default urllib identification received403.

Local verification: 82 Python tests passed, 2 optional tests skipped; 8 Node tests passed; five generated data files reproduced byte-for-byte; nine local HTTP resources passed. Cloud optional solver verification and saved original experiments remain separate evidence.

The account owner confirmed on 2026-11-03 that the original production site opens and interactions work on their phone over mobile data. This user feedback predates the historical enhancement; no fresh user phone acceptance is claimed. Device/browser/carrier were not recorded, and this does not establish every network or browser. Personal career report/PPT and contest submission remain separate.

## Rebuild and hosting

```bash
python tools/build_web.py
python tools/check_web_reproducible.py
node --check web/app.js
node --test tests/test_web.mjs
python tools/check_static_http.py
python -m http.server 8765 --bind 127.0.0.1 --directory web
```

The builder reads committed experiment records from `experiments/chongqing-2026-11-01` and the reviewed aggregate `data/lade-study/public-summary.json`; no private historical records or road service is needed. New baseline experiments require a new directory and `build_web.py --experiments`, plus reviewed geometry as appropriate.

Publish **only `web/`** using the existing account-authorized project:

```bash
wrangler pages deploy web --project-name routeopt-study --branch main
```

Keep index.html, app.js, model.mjs, styles.css and data/ with relative URLs. No framework, external CDN, live map API, API key, backend, database, visitor login or compute instance is required. Do not deploy the repository root, private research files, wheel/build output, credentials or raw task records. Road extracts use ODbL attribution; historical aggregates retain LaDe attribution, license discrepancy and modeling caveats. The application inserts historical text using textContent, validates the aggregate schema, and isolates historical fetch failure from original controls.

## Rollback and verification

Previous immutable deployment https://8c4aa831.routeopt-study.pages.dev/ contains the time/cost module without the historical section (asset source `18133fc`). Older footer/original versions and static ZIPs remain in the private release-backup directory. Re-publish a reviewed previous `web/` archive to the existing Pages project if rollback is needed; preserve its source identity. No account migration, security changes or paid resource is required.

After any relevant release, check scenario/vehicle/overlay/playback/zoom interactions, keyboard/touch and narrow layouts, reduced motion, real download bytes, unusual cost rates, historical disclosures and independent loading failures/recovery. HTTP200 alone does not establish browser behavior. Screenshots and the earlier 15-second actual-playback recording are submission evidence outside the website; older media retain their original release provenance.
