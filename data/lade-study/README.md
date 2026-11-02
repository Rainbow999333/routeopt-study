# Historical task study: data and reproduction

Read [research interpretation](../../docs/lade-research.md) before using the results. This directory contains aggregate statistics and public OSM road extracts, **no parcel positions, order/courier IDs, individual dates or trajectories**. `public-summary.json` is the only historical input to the website.

## Licenses and pinned source

- Research tasks: Wu et al. / Cainiao Network, [LaDe-D](https://huggingface.co/datasets/Cainiao-AI/LaDe-D), revision `e1f85a3339848b9eb606ce543fcaaba3f4be1893`. The HF card says Apache-2.0; the [paper](https://arxiv.org/html/2306.10675v3) specifies CC BY-NC 4.0 for the dataset. Preserve both statements; this project uses attributed non-commercial research and does not redistribute raw tasks. No endorsement implied.
- Source file: `data/delivery_cq-00000-of-00001-465887add76aeabc.parquet`, 61,844,340 bytes; SHA256 `ea503be5d475aa9a3ceb27f09ce6f910f48a02e78122428fbb4f9c724820323b`.
- Roads: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Keep attribution and applicable database obligations on redistribution. MIT applies to code, not these data sources.

`road-snapshots/area1..4.osm` are bounded road-only extracts. Acquisition queries, bounding boxes and source endpoints are in the matching metadata. `saved_extract_sha256` describes the original acquired file; **`redistribution.sanitized_sha256` describes the supplied bytes**. Contributor identity and non-routing address/contact tags are removed. Connectivity and routing rules are preserved. `verification.json` records rebuilding all four sanitized graphs: all 60 quality checks and all selected-case matrix cells matched the private originals. Optimizers were not rerun. Failed groups remain in the redacted quality reports.

## Reproduction (offline research environment)

Base installation and website do not require pandas, Arrow, Docker or OR-Tools. The original research used Linux Python 3.13.5, pandas 3.1.0, pyarrow 26.0.0 and OR-Tools 9.15.6755. Use a separate environment, sufficient disk space and bounded containers. Never serve the research working directory publicly.

1. Obtain the pinned Chongqing source through `python tools/audit_lade.py --directory data/local/lade-research`. The script checks source size/hash and writes private audit files; `data/local/` is ignored. Review upstream terms before acquisition.
2. For each area in order 1,2,3,4, copy its supplied `.osm` into a **new** build directory as `nanan.osm` (the legacy filename is a tool convention, not an area name). Run `python tools/build_osrm_linux.py --directory /absolute/new/areaN`. It pins OSRM image `ghcr.io/project-osrm/osrm-backend@sha256:60a43e45aa42226e76b359ca7308e49be1a41af096bf7b6c9c2a471f0e856078`, uses car.lua and MLD, and refuses an already completed build.
3. Run the pinned image with `osrm-routed --algorithm mld --threads 1 /data/nanan.osrm`, a read-only build-directory mount at `/data`, a loopback-only port, non-root user, dropped capabilities, at most 1 CPU/512MiB. Stop the task container before moving to the next area. Do not expose the server remotely.
4. For each served graph run `python tools/select_lade_roads.py --directory data/local/lade-research --road-metadata data/lade-study/road-snapshots/areaN.meta.json --osrm-url http://127.0.0.1:5075 --label areaN`. These outputs are private; do not copy them directly into Git. The four areas check 35/13/8/4 complete groups; the last selects 21 parcels. Area order and within-area lexicographic order are fixed, not random or globally chronological. No optimization result informs selection.
5. Once only, run the following against area4. A fresh output path is required. Future limited-time OR-Tools runs may differ; retain the first run and report conditions rather than choosing the best.

```bash
python tools/run_lade_case.py \
  --orders-private data/local/lade-research/road-selected-area4-private.json \
  --selection-report data/local/lade-research/road-selection-area4.json \
  --prior-road-reports data/local/lade-research/road-selection-area1.json data/local/lade-research/road-selection-area2.json data/local/lade-research/road-selection-area3.json \
  --osm /absolute/new/area4/nanan.osm --osrm-url http://127.0.0.1:5075 \
  --out-private data/local/lade-case-new
```

6. Keep full routes/matrix/results private. Review only `public-summary.json` for publication using `validate_public_summary`. For quality reports use `public_quality_report` from `tools/sanitize_research_roads.py`: it whitelists **both** the attempts and selected occurrences. The selected dictionary may alias an attempts entry; removing fields only from `selected` leaves timestamps behind. Tests cover this case.
7. Public checks: `python -m pytest -q`, `node --test tests/test_web.mjs`, `python tools/check_web_reproducible.py`. These do not require original parcel records or contact road services.

The source datum remains unconfirmed. WGS84 interpretation, simulated depot, one vehicle/capacity50 and static car travel are assumptions. No raw coordinate conversion, deletion of hard orders or reconstruction of original addresses is performed. This case is counterfactual research, not evidence of actual enterprise dispatch, original route recovery or realized cost savings.
