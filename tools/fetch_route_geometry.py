"""Fetch only used arcs from a local OSRM snapshot, checking geometry length vs matrix."""
import argparse
import json
from pathlib import Path
import urllib.request

from routeopt.export import validate_experiment
from routeopt.io import read_json, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiments", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("geometry snapshot exists; inspect before replacing")
    experiments = sorted(args.experiments.glob("*/result.json"))
    if not 1 <= len(experiments) <= 10:
        raise ValueError("expected 1..10 experiments")
    arcs = set()
    matrix_digest = None
    for path in experiments:
        result = read_json(path)
        scenario, matrix = validate_experiment(result)
        if matrix_digest and matrix_digest != matrix.digest:
            raise ValueError("geometry batch must share the same matrix")
        matrix_digest = matrix.digest
        for run in result["runs"]:
            if run["metrics"]["feasible"]:
                for route in run["routes"]:
                    arcs.update(zip(route, route[1:]))
    if len(arcs) > 400:
        raise ValueError("geometry acquisition limited to 400 arcs")
    stops = {stop.node_id: stop for stop in scenario.stops}
    positions = {n: i for i, n in enumerate(matrix.node_ids)}
    geometry = {}
    max_delta = 0.0
    for a, b in sorted(arcs):
        origin, destination = stops[a], stops[b]
        coordinates = f"{origin.lng},{origin.lat};{destination.lng},{destination.lat}"
        url = "http://127.0.0.1:5071/route/v1/driving/" + coordinates + (
            "?overview=full&geometries=geojson&steps=false&alternatives=false&continue_straight=false")
        with urllib.request.urlopen(url, timeout=20) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("geometry response exceeds 1MiB")
        data = json.loads(raw)
        if data.get("code") != "Ok" or len(data.get("routes", [])) != 1:
            raise ValueError(f"invalid route geometry for {a}->{b}")
        route = data["routes"][0]
        expected = matrix.distances_m[positions[a]][positions[b]]
        delta = abs(route["distance"] - expected)
        if delta > max(1.0, expected * 0.0001):
            raise ValueError(f"geometry/matrix discrepancy for {a}->{b}: {delta}m")
        max_delta = max(max_delta, delta)
        geometry[a + ">" + b] = {"coordinates": route["geometry"]["coordinates"],
                                 "distance_m": route["distance"]}
    write_json(args.out, {"schema_version": "1.0", "matrix_sha256": matrix_digest,
                         "coordinate_system": "WGS84", "geometry_type": "road",
                         "license": "ODbL-1.0", "attribution": "© OpenStreetMap contributors",
                         "max_distance_delta_m": max_delta, "arcs": geometry})
    print(json.dumps({"arcs": len(geometry), "max_distance_delta_m": max_delta}))


if __name__ == "__main__":
    main()
