"""Choose public road nodes BEFORE optimization, verify reachability and save a matrix."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import urllib.request
import xml.etree.ElementTree as ET

from routeopt.io import write_json
from routeopt.matrix import haversine_m
from routeopt.models import Matrix, Scenario, Stop, coordinate_digest

BASE_URL = "http://127.0.0.1:5071"
ALLOWED = {"primary", "secondary", "tertiary", "residential", "unclassified", "living_street"}


def get_json(path):
    with urllib.request.urlopen(BASE_URL + path, timeout=30) as response:
        data = response.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("OSRM response exceeded 8MiB")
    result = json.loads(data)
    if result.get("code") != "Ok":
        raise ValueError(f"OSRM error: {result.get('code')}")
    return result


def spread(candidates, count, initial):
    selected = [initial]
    while len(selected) < count:
        remaining = [node for node in candidates if node not in selected]
        if not remaining:
            break
        distances = [(min(haversine_m(candidates[node][0], candidates[node][1],
                                     candidates[s][0], candidates[s][1]) for s in selected), node)
                     for node in remaining]
        distance, node = max(distances, key=lambda pair: (pair[0], -int(pair[1])))
        if distance < 120:
            break
        selected.append(node)
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--osm", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if (args.out / "matrix.json").exists():
        raise ValueError("snapshot already exists; inspect before replacing")
    root = ET.parse(args.osm).getroot()
    coords = {n.attrib["id"]: (float(n.attrib["lat"]), float(n.attrib["lon"]))
              for n in root.findall("node")}
    neighbors = defaultdict(set)
    for way in root.findall("way"):
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in way.findall("tag")}
        if tags.get("highway") not in ALLOWED:
            continue
        if any(tags.get(field) in {"no", "private"} for field in ("access", "motor_vehicle", "vehicle")):
            continue
        refs = [n.attrib["ref"] for n in way.findall("nd")]
        for a, b in zip(refs, refs[1:]):
            neighbors[a].add(b)
            neighbors[b].add(a)
    candidates = {node: coord for node, coord in coords.items()
                  if len(neighbors[node]) >= 3 and 29.505 <= coord[0] <= 29.545
                  and 106.55 <= coord[1] <= 106.605}
    if len(candidates) < 25:
        raise ValueError("fewer than 25 public road junction candidates")
    depot = min(candidates, key=lambda n: (haversine_m(*candidates[n], 29.525, 106.575), int(n)))
    pool = spread(candidates, 50, depot)
    coordinates = ";".join(f"{candidates[n][1]},{candidates[n][0]}" for n in pool)
    response = get_json("/table/v1/driving/" + coordinates + "?annotations=distance,duration")
    eligible = {}
    for i, node in enumerate(pool):
        snap = max(response["sources"][i]["distance"], response["destinations"][i]["distance"])
        if snap <= 25 and response["durations"][0][i] is not None and response["durations"][i][0] is not None:
            eligible[node] = candidates[node]
    if depot not in eligible or len(eligible) < 25:
        raise ValueError("not enough mutually reachable nodes with <=25m snapping distance")
    selected = spread(eligible, 25, depot)
    if len(selected) != 25:
        raise ValueError("not enough spaced points")
    indices = [pool.index(n) for n in selected]
    if any(response["distances"][i][j] is None for i in indices for j in indices):
        raise ValueError("selected points are not fully mutually reachable")
    rng = random.Random(20261101)
    stops = [Stop("D" if i == 0 else f"O{i:03}", *eligible[node],
                  0 if i == 0 else rng.randint(3, 10)) for i, node in enumerate(selected)]
    scenario = Scenario("chongqing-nanan-24", stops[0], tuple(stops[1:]), 5, 50,
                        "重庆南岸公共道路节点上的模拟配送实验；需求、车辆与仓库用途均为模拟，非企业运营数据。")
    provenance = {"provider": "osrm", "provider_version": "26.10.0-amd64-debian",
                  "profile": "car.lua", "traffic_mode": "car_static", "strategy": "fastest_route",
                  "distance_unit": "m", "duration_unit": "s", "coordinate_system": "WGS84",
                  "coordinates_sha256": coordinate_digest(scenario),
                  "source": "OpenStreetMap via Overpass bounded local extract",
                  "osm_sha256": hashlib.sha256(args.osm.read_bytes()).hexdigest(),
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "license": "ODbL-1.0", "attribution": "© OpenStreetMap contributors",
                  "license_url": "https://www.openstreetmap.org/copyright",
                  "limitations": "Static fastest-path distances on a bounded OSM extract; no live traffic, truck clearance or proof of operational feasibility."}
    matrix = Matrix(tuple(s.node_id for s in stops),
                    tuple(tuple(response["distances"][i][j] for j in indices) for i in indices),
                    provenance,
                    tuple(tuple(response["durations"][i][j] for j in indices) for i in indices))
    matrix.validate_for(scenario)
    write_json(args.out / "scenario.json", scenario.to_dict())
    write_json(args.out / "matrix.json", matrix.to_dict())
    selected_nodes = [{"node_id": stop.node_id, "osm_node_id": node,
                       "snap_distance_m": max(response["sources"][i]["distance"],
                                              response["destinations"][i]["distance"])}
                      for stop, node, i in zip(stops, selected, indices)]
    quality = {"candidate_junctions": len(candidates), "candidate_pool": len(pool),
               "eligible_pool": len(eligible), "selection": "deterministic spatial farthest sampling, before optimization",
               "demand_seed": 20261101, "total_demand": sum(s.demand for s in stops),
               "selected_nodes": selected_nodes, "all_pairs_reachable": True,
               "asymmetric_pairs": sum(abs(matrix.distances_m[i][j] - matrix.distances_m[j][i]) > 1
                                        for i in range(25) for j in range(i + 1, 25)),
               "matrix_sha256": matrix.digest, "scenario_sha256": scenario.digest}
    write_json(args.out / "quality.json", quality)
    print(json.dumps({k: v for k, v in quality.items() if k != "selected_nodes"}))


if __name__ == "__main__":
    main()
