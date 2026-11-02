"""Audit a pinned Chongqing research dataset without publishing raw order records.

Requires pyarrow and pandas only in the offline research environment.
The source's paper and HF card differ on licensing; apply attributed,
non-commercial research use, retain both statements, and do not bundle raw data.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

REVISION = "e1f85a3339848b9eb606ce543fcaaba3f4be1893"
FILENAME = "data/delivery_cq-00000-of-00001-465887add76aeabc.parquet"
REPOSITORY = "https://huggingface.co/datasets/Cainiao-AI/LaDe-D"
MAX_BYTES = 70 * 1024 * 1024


def fetch(url, maximum):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "routeopt-study-research/0.1"}), timeout=90) as r:
        data = r.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("source response exceeds bounded size")
    return data


def download(directory):
    directory.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(directory)
    if disk.used / disk.total >= .8 or disk.free < 1024 ** 3:
        raise RuntimeError("research disk needs <80% use and 1GiB free")
    metadata = json.loads(fetch(f"https://huggingface.co/api/datasets/Cainiao-AI/LaDe-D/tree/{REVISION}/data", 1024 * 1024))
    entry = next(v for v in metadata if v["path"] == FILENAME)
    expected = entry["lfs"]["oid"]
    path = directory / "delivery_cq.parquet"
    if not path.exists():
        payload = fetch(f"{REPOSITORY}/resolve/{REVISION}/{FILENAME}", MAX_BYTES)
        if len(payload) != entry["size"] or hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError("official source size/hash mismatch")
        path.write_bytes(payload)
    if path.stat().st_size > MAX_BYTES or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("existing source differs from pinned source")
    card = directory / "source-card.md"
    if not card.exists():
        card.write_bytes(fetch(f"{REPOSITORY}/resolve/{REVISION}/README.md", 65536))
    return path, expected


def main():
    import pandas as pd
    import pyarrow
    import pyarrow.parquet as pq

    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True, help="private research working directory")
    args = parser.parse_args()
    summary_path = args.directory / "audit-summary.json"
    if summary_path.exists():
        raise ValueError("audit exists; preserve it and choose a new directory")
    path, digest = download(args.directory)
    columns = ["order_id", "region_id", "city", "courier_id", "lng", "lat", "accept_time", "delivery_time", "ds"]
    df = pq.read_table(path, columns=columns).to_pandas()
    total = len(df)
    if set(df["city"].dropna()) != {"Chongqing"}:
        raise ValueError("source is not exclusively Chongqing")
    keys = ["ds", "region_id", "courier_id"]
    source_counts = df.groupby(keys).size()
    valid = df["lng"].between(105, 111) & df["lat"].between(28, 33)
    df = df[valid].copy()
    for field in ("accept_time", "delivery_time"):
        df[field + "_parsed"] = pd.to_datetime(df[field], format="%m-%d %H:%M:%S", errors="coerce")
    valid_times = (df["accept_time_parsed"].notna() & df["delivery_time_parsed"].notna()
                   & (df["accept_time_parsed"] <= df["delivery_time_parsed"]))
    df = df[valid_times].copy()
    # Group only exact released positions; never decode or reconstruct privacy offsets.
    df["stop_key"] = list(zip(df["lng"], df["lat"]))
    batches = df.groupby(keys, sort=True).agg(
        orders=("order_id", "size"), unique_orders=("order_id", "nunique"),
        stops=("stop_key", "nunique"), max_accept=("accept_time_parsed", "max"),
        first_delivery=("delivery_time_parsed", "min"),
        min_lng=("lng", "min"), max_lng=("lng", "max"),
        min_lat=("lat", "min"), max_lat=("lat", "max"))
    candidates = batches[(batches["stops"].between(20, 30))
                         & (batches["orders"] == source_counts.reindex(batches.index))
                         & (batches["orders"] == batches["unique_orders"])
                         & (batches["max_accept"] <= batches["first_delivery"])
                         & ((batches["max_lng"] - batches["min_lng"]) <= .04)
                         & ((batches["max_lat"] - batches["min_lat"]) <= .04)]
    summary = {
        "source_repository": REPOSITORY, "revision": REVISION, "source_file": FILENAME,
        "source_sha256": digest, "source_bytes": path.stat().st_size,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": {"pandas": pd.__version__, "pyarrow": pyarrow.__version__},
        "license_hf_card": "Apache-2.0", "license_paper": "CC BY-NC 4.0",
        "usage": "attributed non-commercial research; raw data not included in public repository or website",
        "rows": total, "invalid_coordinate_rows": int((~valid).sum()),
        "invalid_or_reversed_time_rows": int((~valid_times).sum()), "usable_rows": len(df),
        "courier_region_day_groups": len(batches), "eligible_complete_groups": len(candidates),
        "selection_rule": "First lexicographic (ds, region_id, courier_id) full valid group with 20..30 exact positions, all tasks accepted no later than first completion, no duplicate order IDs, span<=0.04 degrees each; before route optimization",
        "coordinate_status": "Released perturbed coordinates; numeric bounds checked, geographic CRS/alignment still needs validation",
        "missing_business_fields": ["depot", "vehicle capacity", "weights", "cost rates", "promised delivery windows", "service durations"],
    }
    if len(candidates):
        key = candidates.index[0]
        selected = df[(df["ds"] == key[0]) & (df["region_id"] == key[1]) & (df["courier_id"] == key[2])].sort_values(["delivery_time_parsed", "order_id"])
        # Recheck against the complete source group: missing rows must not silently disappear.
        source_table = pq.read_table(path, columns=columns).to_pandas()
        original = source_table[(source_table["ds"] == key[0]) & (source_table["region_id"] == key[1]) & (source_table["courier_id"] == key[2])]
        if len(original) != len(selected):
            raise ValueError("selected group has invalid source rows; revise explicit eligibility, do not silently drop")
        records = selected[columns].to_dict(orient="records")
        raw = json.dumps(records, ensure_ascii=False, indent=2).encode()
        (args.directory / "selected-private.json").write_bytes(raw)
        summary["selected"] = {
            "orders": len(selected), "unique_stops": int(selected["stop_key"].nunique()),
            "private_selection_sha256": hashlib.sha256(raw).hexdigest(),
            "batch_ds": int(key[0]), "all_tasks_known_by_first_completion": True,
            "bbox": [float(selected.lat.min()), float(selected.lng.min()), float(selected.lat.max()), float(selected.lng.max())],
            "max_accept": str(selected["accept_time_parsed"].max()),
            "first_completion": str(selected["delivery_time_parsed"].min()),
            "release_warning": "timestamps lack year here; 1900 is a parser placeholder, not observation year",
        }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
