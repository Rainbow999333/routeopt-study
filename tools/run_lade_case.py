"""A private historical-task counterfactual; public output contains aggregates only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
import urllib.request
import xml.etree.ElementTree as ET

from routeopt.decision import decision_summary
from routeopt.experiment import compare, markdown_report
from routeopt.export import validate_experiment
from routeopt.io import read_json, write_json
from routeopt.matrix import haversine_m
from routeopt.models import Matrix, Scenario, Stop, coordinate_digest

PUBLIC_FIELDS = {"schema_version", "case_id", "study_type", "orders", "positions", "simulated_depots", "assumed_capacity_items", "assumed_max_vehicles", "matrix_sha256", "scenario_sha256", "source_repository", "source_revision", "source_sha256", "selected_source_sha256", "quality", "data_notice", "assumptions", "runs"}


def validate_public_summary(value):
    if set(value) != PUBLIC_FIELDS or value["study_type"] != "historical_tasks_counterfactual_routing":
        raise ValueError("unexpected public historical summary fields")
    forbidden = {"lat", "lng", "stops", "routes", "order_id", "courier_id", "region_id", "aoi_id", "accept_time", "delivery_time", "ds"}
    def walk(item):
        if isinstance(item, dict):
            if set(item) & forbidden:
                raise ValueError("private order fields in public summary")
            for child in item.values(): walk(child)
        elif isinstance(item, list):
            for child in item: walk(child)
    walk(value)
    quality = value["quality"]
    if quality["threshold_m"] != 50 or not 0 <= quality["max_snap_m_including_depot"] <= 50 or quality["all_pairs_reachable"] is not True or quality["selection_before_solving"] is not True:
        raise ValueError("public historical case did not pass road gate")
    return value


def validate_records(rows):
    if not isinstance(rows, list) or not 20 <= len(rows) <= 500:
        raise ValueError("20..500 complete source parcel records required")
    if len({r["order_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate source order")
    if len({(r["ds"], r["region_id"], r["courier_id"]) for r in rows}) != 1:
        raise ValueError("source rows must form one complete date/region/courier group")
    # 2000 is solely a leap-safe parser epoch; it is not the observation year.
    times = lambda field: [datetime.strptime("2000-" + r[field], "%Y-%m-%d %H:%M:%S") for r in rows]
    accepted, completed = times("accept_time"), times("delivery_time")
    if any(a > d for a, d in zip(accepted, completed)) or max(accepted) > min(completed):
        raise ValueError("not all tasks known by assumed static decision time")
    positions = {}
    for row in rows:
        point = Stop("check", row["lat"], row["lng"], 1)
        key = point.lat, point.lng
        positions[key] = positions.get(key, 0) + 1
    if not 20 <= len(positions) <= 30:
        raise ValueError("complete group must have 20..30 exact released positions")
    stops = tuple(Stop(f"O{i+1:03}", lat, lng, count) for i, ((lat, lng), count) in enumerate(positions.items()))
    return stops


def loopback_base(value):
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("only a local HTTP OSRM origin is allowed for private positions")
    return value.rstrip("/")


def public_summary(result, quality, selection):
    scenario, matrix = validate_experiment(result)
    decisions = decision_summary(result)["runs"]
    return {
        "schema_version": "1.0", "case_id": f"lade-chongqing-historical-{len(scenario.orders)}",
        "study_type": "historical_tasks_counterfactual_routing",
        "orders": sum(s.demand for s in scenario.orders), "positions": len(scenario.orders), "simulated_depots": 1,
        "assumed_capacity_items": scenario.capacity, "assumed_max_vehicles": scenario.max_vehicles,
        "matrix_sha256": matrix.digest, "scenario_sha256": scenario.digest,
        "source_repository": "https://huggingface.co/datasets/Cainiao-AI/LaDe-D",
        "source_revision": "e1f85a3339848b9eb606ce543fcaaba3f4be1893",
        "source_sha256": "ea503be5d475aa9a3ceb27f09ce6f910f48a02e78122428fbb4f9c724820323b",
        "selected_source_sha256": selection["source_group_sha256"],
        "quality": {key: quality[key] for key in ("threshold_m", "max_snap_m_including_depot", "all_pairs_reachable", "selected_after_quality_attempts", "selection_before_solving", "coordinate_datum_confirmed")},
        "data_notice": {"creators": "Wu et al. / Cainiao Network, LaDe",
                        "paper": "https://arxiv.org/abs/2306.10675",
                        "paper_dataset_license": "CC BY-NC 4.0", "hf_card_license": "Apache-2.0",
                        "use": "attributed non-commercial research; raw records and positions not redistributed"},
        "assumptions": ["公开脱敏历史任务，不是本人企业实习或现场配送验证。",
                        "发布坐标按WGS84解释是建模假设，源坐标基准尚未明确；吸附通过不等于基准已证实。",
                        "仓库取公共道路节点作模拟起终点；1辆车、50件容量为实验参数，不是实际车队数据。",
                        "每条包裹记录记1件；试验决策时刻设为该批最后接收时刻，不断言真实出车时刻。",
                        "采用当前OSM静态car.lua路网；未还原历史路况、车辆方式、停车、服务和承诺时间窗。"],
        "runs": [{"solver": r["solver"], "feasible": r["metrics"]["feasible"], "solver_elapsed_s": r["elapsed_s"], "time_limit_s": r["parameters"].get("time_limit_s"),
                  "improvement_pct": r["improvement_pct"], **decisions.get(r["solver"], {})}
                 for r in result["runs"]],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders-private", type=Path, required=True)
    parser.add_argument("--selection-report", type=Path, required=True)
    parser.add_argument("--osm", type=Path, required=True)
    parser.add_argument("--osrm-url", default="http://127.0.0.1:5075")
    parser.add_argument("--out-private", type=Path, required=True)
    parser.add_argument("--prior-road-reports", nargs="*", type=Path, default=[])
    args = parser.parse_args()
    base = loopback_base(args.osrm_url)
    if args.out_private.exists():
        raise ValueError("case output exists; inspect and choose a new directory")
    if args.orders_private.stat().st_size > 256 * 1024 or args.osm.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("research input too large")
    raw = args.orders_private.read_bytes()
    selection_report = read_json(args.selection_report)
    selection = selection_report["selected"]
    if hashlib.sha256(raw).hexdigest() != selection["source_group_sha256"]:
        raise ValueError("private input differs from the quality-selected group")
    stops = validate_records(json.loads(raw))
    if sum(s.demand for s in stops) != selection["orders"] or len(stops) != selection["stops"] or selection["max_snap_m"] > 50 or selection["unreachable_cells"]:
        raise ValueError("selection quality gate did not pass")
    osm = ET.parse(args.osm).getroot()
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon"))) for n in osm.findall("node")}
    neighbors = {}
    for way in osm.findall("way"):
        refs = [n.get("ref") for n in way.findall("nd")]
        for a, b in zip(refs, refs[1:]):
            neighbors.setdefault(a, set()).add(b); neighbors.setdefault(b, set()).add(a)
    center = (sum(s.lat for s in stops)/len(stops), sum(s.lng for s in stops)/len(stops))
    candidates = [node for node, adjacent in neighbors.items() if len(adjacent) >= 3]
    node = min(candidates, key=lambda node: (haversine_m(*nodes[node], *center), int(node)))
    scenario = Scenario(f"lade-chongqing-private-{len(stops)}", Stop("D", *nodes[node]), stops, 1, 50,
        "Public perturbed historical parcel tasks; simulated depot/capacity/car mode; released values interpreted as WGS84, datum unconfirmed; counterfactual research, not observed dispatch performance.")
    coordinates = ";".join(f"{s.lng},{s.lat}" for s in scenario.stops)
    with urllib.request.urlopen(base + "/table/v1/driving/" + coordinates + "?annotations=distance,duration", timeout=20) as r:
        response = r.read(1024*1024+1)
    if len(response) > 1024*1024:
        raise ValueError("local matrix response exceeds limit")
    data = json.loads(response)
    if data.get("code") != "Ok":
        raise ValueError("local OSRM rejected matrix")
    snaps = [max(a["distance"], b["distance"]) for a,b in zip(data["sources"], data["destinations"])]
    if max(snaps) > 50 or any(v is None for row in data["distances"] for v in row):
        raise ValueError("complete case including simulated depot did not pass road quality gate")
    provenance = {"provider": "osrm", "provider_version": "26.10.0-amd64-debian", "profile": "car.lua",
        "traffic_mode": "car_static", "strategy": "fastest_route", "distance_unit": "m", "duration_unit": "s",
        "coordinate_system": "WGS84", "coordinates_sha256": coordinate_digest(scenario),
        "input_datum_assumption": "released values interpreted as WGS84; actual source datum unconfirmed",
        "source": "OSM current bounded extract; private LaDe released task positions",
        "osm_sha256": hashlib.sha256(args.osm.read_bytes()).hexdigest(), "license": "ODbL-1.0",
        "source_task_terms": "LaDe research, see paper CC BY-NC 4.0 and conflicting HF card Apache-2.0",
        "created_at": datetime.now(timezone.utc).isoformat()}
    matrix = Matrix(tuple(s.node_id for s in scenario.stops), tuple(tuple(r) for r in data["distances"]),
                    provenance, tuple(tuple(r) for r in data["durations"]))
    result = compare(scenario, matrix, solvers=("nn", "2opt", "ortools"), repeat=1)
    if not all(r["metrics"]["feasible"] for r in result["runs"]):
        raise ValueError("case did not pass all requested solver validations")
    attempts = len(selection_report["attempts"]) + sum(len(read_json(path)["attempts"]) for path in args.prior_road_reports)
    quality = {"threshold_m": 50, "max_snap_m_including_depot": max(snaps), "all_pairs_reachable": True,
               "selected_after_quality_attempts": attempts, "selection_before_solving": True,
               "coordinate_datum_confirmed": False}
    summary = public_summary(result, quality, selection)
    validate_public_summary(summary)
    write_json(args.out_private / "result-private.json", result)
    write_json(args.out_private / "public-summary.json", summary)
    (args.out_private / "comparison-private.md").write_text(markdown_report(result), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
