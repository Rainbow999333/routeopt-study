import hashlib
from pathlib import Path

from routeopt.evaluate import evaluate
from routeopt.io import read_json
from routeopt.models import Matrix, Scenario
from routeopt.solver import nearest_neighbor, two_opt

DATA = Path(__file__).resolve().parents[1] / "data" / "chongqing"


def test_saved_road_snapshot_integrity_and_direction():
    scenario = Scenario.from_dict(read_json(DATA / "scenario.json"))
    matrix = Matrix.from_dict(read_json(DATA / "matrix.json"))
    quality = read_json(DATA / "quality.json")
    matrix.validate_for(scenario)
    assert matrix.digest == quality["matrix_sha256"]
    assert scenario.digest == quality["scenario_sha256"]
    assert len(scenario.orders) == 24
    assert all(value is not None for row in matrix.distances_m for value in row)
    assert all(point["snap_distance_m"] <= 25 for point in quality["selected_nodes"])
    assert quality["asymmetric_pairs"] == 296
    extract = DATA / "source" / "nanan-2026-11-01.osm"
    assert hashlib.sha256(extract.read_bytes()).hexdigest() == matrix.provenance["osm_sha256"]


def test_actual_road_results_and_geometry_recompute():
    scenario = Scenario.from_dict(read_json(DATA / "scenario.json"))
    matrix = Matrix.from_dict(read_json(DATA / "matrix.json"))
    baseline = nearest_neighbor(scenario, matrix)
    optimized = two_opt(scenario, matrix, baseline)
    a, b = evaluate(scenario, matrix, baseline), evaluate(scenario, matrix, optimized)
    assert a["feasible"] and b["feasible"]
    assert round(a["distance_km"], 3) == 77.510
    assert round(b["distance_km"], 3) == 72.920
    geometry = read_json(DATA / "road-geometry.json")
    assert geometry["matrix_sha256"] == matrix.digest
    for arc, data in geometry["arcs"].items():
        origin, destination = arc.split(">")
        i, j = matrix.node_ids.index(origin), matrix.node_ids.index(destination)
        assert abs(data["distance_m"] - matrix.distances_m[i][j]) <= 1
