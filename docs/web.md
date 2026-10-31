# Static website

Build after generating the verified scenario runs:

```bash
python tools/run_chongqing.py --input data/chongqing --out out/chongqing
python tools/build_web.py
node --check web/app.js
node --test tests/test_web.mjs
python -m http.server 8765 --bind 127.0.0.1 --directory web
```

Publish only web/ to Cloudflare Pages or ModelScope Static. No runtime framework, external CDN, hosted map, API key, account login, compute instance or online solver is needed for visitors. Browser interaction selects precomputed scenarios; it does not claim to rerun optimization.

The static directory includes reviewed scenarios, road geometry, an OSM background road network and CSV comparisons. All URLs are relative and no SPA route fallback is required. Preserve index.html, app.js, model.mjs, styles.css and data/.

Road data uses ODbL-1.0 with attribution. Review every source field before publishing. Do not deploy the repository root, private local files, wheel/build output or complete experiment directories. Local data has been selected from public OSM road nodes and simulated item demand; no customer data or third-party map credentials.

Browser verification must cover scenario selection, NN/2-opt overlays, vehicle highlight, playback/pause, zoom/reset, downloads, keyboard focus, narrow/mobile/desktop widths, reduced motion and missing data. A terminal test or successful static HTTP response alone does not prove these.
