"""Build a reviewed, portable static publication directory from verified experiments."""
import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from routeopt.export import public_result, validate_experiment
from routeopt.io import read_json
from routeopt.decision import decision_summary


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                    encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiments", type=Path, default=Path("experiments/chongqing-2026-11-01"))
    parser.add_argument("--out", type=Path, default=Path("web/data"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    geometry = read_json(root / "data/chongqing/road-geometry.json")
    cases = []
    for key, title in [("standard", "标准车队"), ("small-vehicle", "小容量车辆"),
                       ("large-vehicle", "大容量车辆"), ("higher-demand", "较高需求")]:
        result = read_json(args.experiments / key / "result.json")
        scenario, matrix = validate_experiment(result)
        if geometry["matrix_sha256"] != matrix.digest:
            raise ValueError("geometry snapshot does not match experiment matrix")
        for run in result["runs"]:
            if not run["metrics"]["feasible"]:
                continue
            for route in run["routes"]:
                positions = {n: i for i, n in enumerate(matrix.node_ids)}
                for a, b in zip(route, route[1:]):
                    arc = geometry["arcs"][a + ">" + b]
                    expected = matrix.distances_m[positions[a]][positions[b]]
                    if abs(arc["distance_m"] - expected) > max(1, expected * 0.0001):
                        raise ValueError("road geometry distance mismatch")
        public = public_result(result, approved=True)
        # Road geometries are stored once across all scenarios.
        public.pop("geometry")
        public.update(key=key, title=title, total_demand=sum(s.demand for s in scenario.orders),
                      decision=decision_summary(result))
        cases.append(public)
    save(args.out / "scenarios.json", {"schema_version": "1.0", "scenarios": cases})
    save(args.out / "geometry.json", geometry)
    osm = ET.parse(root / "data/chongqing/source/nanan-2026-11-01.osm").getroot()
    nodes = {n.get("id"): [float(n.get("lon")), float(n.get("lat"))] for n in osm.findall("node")}
    roads = []
    for way in osm.findall("way"):
        refs = [node.get("ref") for node in way.findall("nd")]
        if all(ref in nodes for ref in refs):
            roads.append([nodes[ref] for ref in refs])
    save(args.out / "roads.json", {"license": "ODbL-1.0",
                                 "attribution": "© OpenStreetMap contributors", "roads": roads})
    with (args.out / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["scenario", "algorithm", "feasible", "distance_km", "vehicles_used",
                         "load_pct", "solver_elapsed_s", "improvement_pct", "matrix_sha256"])
        for case in cases:
            for run in case["runs"]:
                m = run["metrics"]
                writer.writerow([case["key"], run["solver"], m["feasible"], m["distance_km"],
                                 m["vehicles_used"], m["average_load_pct"], m["solver_elapsed_s"],
                                 run["improvement_pct"], case["matrix_sha256"]])
    print(json.dumps({"scenarios": len(cases), "road_arcs": len(geometry["arcs"]),
                      "background_roads": len(roads), "publication_directory": str(args.out)}))


if __name__ == "__main__":
    main()
