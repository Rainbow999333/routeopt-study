# LaDe Chongqing research audit

This is an additional research track, separate from the existing Nan'an road experiment. No historical-order route result has passed publication review yet. The existing experiment remains **real public roads with simulated demand**.

Source: [Cainiao-AI/LaDe-D](https://huggingface.co/datasets/Cainiao-AI/LaDe-D), revision `e1f85a3339848b9eb606ce543fcaaba3f4be1893`, Chongqing Parquet only (61,844,340 bytes, SHA256 `ea503be5d475aa9a3ceb27f09ce6f910f48a02e78122428fbb4f9c724820323b`).

The HF card labels Apache-2.0; the [authors' paper](https://arxiv.org/html/2306.10675v3) specifies CC BY-NC 4.0 for the dataset. We record the discrepancy and limit this work to attributed non-commercial research, following the more restrictive stated use. Raw order records, courier identifiers, individual timestamps and trajectories are not included in this code repository or the public website. No endorsement or business relationship with Cainiao is implied.

The paper describes privacy perturbations. A latitude/longitude range check does not establish the coordinate reference system or justify reconstructing original customer locations. Public-road alignment must be checked separately; no silent coordinate conversion or point relocation is allowed.

## Pre-optimization selection

1. Validate the pinned source size/hash; do not replace a different local input silently.
2. Group by the released date, region and courier. Reject an entire group if it contains invalid coordinates/times or duplicate order IDs; do not quietly discard bad rows from an otherwise retained group.
3. Keep complete groups with 20–30 distinct released positions, all acceptance events no later than the first completion, and a maximum span of 0.04 degrees per dimension.
4. Inspect groups in fixed lexicographic order. Acquire only buffered local road extracts, test all retained positions at a maximum **50 m** road-snap distance and require all-pairs reachability. Record every exclusion before running an optimizer. The user explicitly chose to preserve this gate and continue checking complete groups.

The corrected full-source audit found 931,351 rows; 93 failed the broad coordinate-range check and 3 more had invalid/reversed times. There are 999 eligible complete groups before road validation. The earlier weaker count of 1,006 is superseded because groups containing removed rows must also be excluded.

The first 22-position batch failed the road gate (two positions >50 m, maximum 89.84 m). All 35 eligible groups within that first buffered extract failed; a second extract also produced no passing group among its 13 eligible groups. No order was dropped to make a batch pass. These checks show a modeling/road-alignment limitation, not incorrect delivery by the original courier.

## Interpretation gates

Even a passing snap test does not prove the source datum, original depot or vehicle type. A complete set accepted before its first completion is not proof that every task was known at actual departure. Any later experiment must state its assumed decision time, depot, transport mode and capacity separately. Completion timestamps are observations, not promised time windows; accept-to-complete time is not pure driving time. Neither historical-order sorting nor the resulting shortest modeled route establishes real cash savings.

Offline audit command (requires pandas/pyarrow in a research environment, tested with pandas 3.1.0 and pyarrow 26.0.0):

```bash
python tools/audit_lade.py --directory data/local/lade-research
```

The input is intentionally excluded by `data/local/`. Audit output remains private until field-level publication review; code MIT licensing does not relicense upstream data. Existing road/scenario archives are never overwritten by this research track.
