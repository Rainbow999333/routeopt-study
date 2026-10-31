# Verified results (2026-11-01)

Public road junctions, simulated item demand, single-trip return-to-depot CVRP. Static OSRM car-profile fastest-path distances on a bounded OSM extract. No live traffic or real fleet validation.

| Record | NN km | 2-opt km | OR-Tools km | Time budget |
|---|---:|---:|---:|---|
| Optional Linux standard comparison | 77.510 | 72.920 | 56.620 | OR-Tools: 3 seconds |

All three solutions passed the same independent coverage/capacity/return/reachability checks and used 3 vehicles with 94% average load. OR-Tools changes global assignment/search; route-local 2-opt preserves NN vehicle membership. The OR-Tools distance reduction is 26.952% relative to NN, not a claim of optimality or operating cost savings.

Raw record: [optional-linux-ortools.json](../experiments/chongqing-2026-11-01/optional-linux-ortools.json). The optional dependency was 9.15.6755 on Linux/Python 3.13.5; Windows NN/2-opt timings from other records are not controlled cross-platform timing comparisons.

The four website scenarios are kept separately under [experiment records](../experiments/chongqing-2026-11-01). They all use the same matrix fingerprint. The higher-demand scenario multiplies each simulated item count by 1.3 and rounds; its total is 181 versus 141 in the base case, so the aggregate increase is about 28.4%, not exactly 30%.

Two useful limitations demonstrated by the data:

1. Of 300 unordered point pairs, 296 have more than a metre of directional distance difference. Symmetric TSP shortcuts cannot be assumed.
2. Raising capacity from 50 to 70 does not automatically improve a nearest-neighbor heuristic: the route split changes and observed NN distance grows from 77.510 to 85.683 km. Total demand 141 still requires at least three 70-item vehicles. This is a heuristic/scenario observation, not evidence that larger trucks are intrinsically less efficient.

Dataset selection preceded optimization and used spatial dispersion, snapping and reachability, not improvement percentages. No minimum gain was selected as a publication threshold.

Figures can be regenerated using the optional Matplotlib dependency:

```bash
python -m pip install -e ".[figures]"
python tools/plot_evidence.py --out out/figures
```
