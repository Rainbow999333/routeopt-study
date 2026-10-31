# Static website

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
