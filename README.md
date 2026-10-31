# routeopt

A reproducible toolkit for last-mile delivery route optimization: compare a capacity-constrained nearest-neighbor baseline with directed-safe 2-opt, validate solutions independently, and export experiment records.

## Quick start

Python 3.11+; the base toolkit has no runtime dependencies.

```bash
python -m pip install -e .
routeopt demo
routeopt demo --out out/demo.json
routeopt export --input out/demo.json --format geojson --out out/routes.geojson
routeopt export --input out/demo.json --format markdown --out out/comparison.md
```

The bundled 24-order scenario is synthetic. Haversine distances are spherical approximations, **not road distances**. GeoJSON connections show visit order, not navigation paths.

## Chongqing road experiment

The repository also includes 24 public OSM road junctions plus one simulated depot in Nan'an, Chongqing, with simulated item demand. A local OSRM 26.10.0 car-profile snapshot supplies the same directed matrix for every algorithm. These are not real business orders or a field deployment.

| Scenario | NN km | NN + 2-opt km | Reduction | Used vehicles |
|---|---:|---:|---:|---:|
| Standard, capacity 50 | 77.510 | 72.920 | 5.921% | 3 → 3 |
| Smaller vehicles, capacity 35 | 96.707 | 92.777 | 4.064% | 5 → 5 |
| Larger vehicles, capacity 70 | 85.683 | 81.374 | 5.029% | 3 → 3 |
| Higher simulated demand | 85.888 | 75.682 | 11.883% | 4 → 4 |

These are measured snapshot results. Lower distance is not evidence of lower fleet size or operating cost. In particular, a different capacity can change a greedy initial solution in unexpected ways. No global optimality is claimed.

```bash
routeopt compare --scenario data/chongqing/scenario.json --matrix data/chongqing/matrix.json --repeat 5 --out out/roads.json
python tools/run_chongqing.py --input data/chongqing --out out/new-experiment
python tools/build_web.py --experiments out/new-experiment
python -m http.server 8765 --bind 127.0.0.1 --directory web
```

See [data provenance and limitations](data/chongqing/README.md), [method](docs/method.md) and [website instructions](docs/web.md). All 625 matrix cells are reachable; 296 of 300 unordered point pairs have direction-dependent distances greater than 1 metre. Road geometry on the webpage was checked against 84 used matrix arcs with zero difference at API precision. CI verifies saved inputs without querying any road service.

```bash
routeopt compare --scenario data/sample/scenario.json --solvers nn,2opt --repeat 5 --out out/result.json
routeopt solve --scenario data/sample/scenario.json --solver 2opt --out out/solution.json
routeopt compare --scenario data/sample/scenario.json --matrix data/sample/matrix.json --out out/roads.json
```

The matrix argument loads an offline snapshot; no network service is contacted. IDs, coordinate fingerprints and units are checked. Every output includes input hashes, algorithm parameters, timings and independent validation. Input and saved result schemas are versioned at 1.0.

## Model and limitations

- Single depot, homogeneous fleet, single trip, return to depot, capacity in items. Every order must be served exactly once.
- Minimize total distance under a vehicle upper bound. Do not infer fleet reduction or cost savings from route-local 2-opt.
- No time windows, truck restrictions, live traffic, multi-depot routing or operational dispatch claims.
- NN may fail to find a feasible packing even if one exists; failures are not mathematical infeasibility proofs.
- 2-opt evaluates full directed reversal costs; it never applies the symmetric four-edge shortcut.
- Deterministic repetitions measure timing variation, not independent evidence of solution quality.
- OR-Tools is optional: install `.[ortools]`, then use `--solvers nn,2opt,ortools`. Missing dependency is reported as skipped. Its integer adapter rounds distance to metres and re-evaluates metrics on the original matrix.

## Public data

Public export requires `--approved-public-data` after manual data/license review:

```bash
routeopt export --input out/demo.json --format public --approved-public-data --out out/public.json
```

It uses an explicit field whitelist. This is not automatic anonymization; coordinates, node IDs and descriptions must be reviewed. Matrices and arbitrary provenance are excluded. GeoJSON/Markdown exports are analysis outputs and require the same review before publishing.

Code: MIT. Synthetic sample: CC0-1.0. OSM road extracts and applicable derived databases use ODbL-1.0 and need separate attribution. No AMap data or keys are included.

## Tests

```bash
python -m pip install -e ".[test]"
python -m pytest
```

The suite checks directed matrices, capacity, unreachable arcs, duplicate/missing orders, depot return, input validation, result tampering, public export, saved road snapshot integrity and a complete CLI workflow. Optional OR-Tools tests are skipped when it is not installed; the base NN/2-opt workflow is fully offline.
