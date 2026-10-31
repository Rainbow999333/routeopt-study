from dataclasses import replace
import json
import math
import random

import pytest

from routeopt.cli import main
from routeopt.evaluate import evaluate, improvement_pct
from routeopt.experiment import compare
from routeopt.export import geojson, public_result, validate_experiment
from routeopt.io import read_json, write_json
from routeopt.matrix import haversine_m, haversine_matrix
from routeopt.models import Matrix, Scenario, Stop, coordinate_digest
from routeopt.solver import Solution, nearest_neighbor, route_cost, two_opt


def scenario(demands=(1, 1, 1, 1), capacity=3, vehicles=2):
    return Scenario("test", Stop("D", 0, 0),
                    tuple(Stop(f"O{i}", 0.01 * (i + 1), 0.02 * (i % 2 + 1), demand)
                          for i, demand in enumerate(demands)), vehicles, capacity)


def custom_matrix(s, values):
    return Matrix(tuple(x.node_id for x in s.stops), tuple(tuple(r) for r in values),
                  {"provider": "test", "coordinates_sha256": coordinate_digest(s)})


def test_haversine_known_distance():
    assert haversine_m(0, 0, 0, 1) == pytest.approx(111195.08, abs=0.1)
    assert haversine_m(12, 40, 12, 40) == 0


@pytest.mark.parametrize("field,value", [
    ("lat", 91), ("lng", -181), ("demand", -1), ("demand", float("nan")),
    ("lat", float("inf")), ("demand", True), ("node_id", ""),
])
def test_invalid_stop(field, value):
    fields = dict(node_id="A", lat=0, lng=0, demand=1)
    fields[field] = value
    with pytest.raises(ValueError):
        Stop(**fields)


@pytest.mark.parametrize("change", [
    {"capacity": 0}, {"max_vehicles": 0}, {"max_vehicles": True},
    {"coordinate_system": "GCJ02"}, {"demand_unit": "kg"},
])
def test_invalid_scenario(change):
    with pytest.raises(ValueError):
        replace(scenario(), **change)


def test_duplicate_id_and_depot_demand():
    s = scenario()
    with pytest.raises(ValueError):
        replace(s, orders=(s.orders[0], s.orders[0]))
    with pytest.raises(ValueError):
        replace(s, depot=Stop("D", 0, 0, 1))


def test_unsupported_constraints_are_not_silently_ignored():
    data = scenario().to_dict()
    data["time_windows"] = [0, 50]
    with pytest.raises(ValueError, match="unsupported"):
        Scenario.from_dict(data)


@pytest.mark.parametrize("values", [
    [[0, 1], [1]], [[0, -1], [1, 0]], [[0, float("inf")], [1, 0]],
    [[1, 2], [2, 0]],
])
def test_invalid_matrix(values):
    with pytest.raises(ValueError):
        custom_matrix(scenario((1,)), values)


def test_node_order_and_coordinate_fingerprint():
    s = scenario()
    matrix = haversine_matrix(s)
    changed = replace(s, orders=tuple(reversed(s.orders)))
    with pytest.raises(ValueError, match="order"):
        matrix.validate_for(changed)
    moved = replace(s, orders=(replace(s.orders[0], lat=1),) + s.orders[1:])
    with pytest.raises(ValueError, match="coordinate"):
        matrix.validate_for(moved)
    matrix.validate_for(replace(s, capacity=10))  # Same roads, different capacity is valid.


def test_capacity_constrained_baseline():
    s = scenario()
    matrix = haversine_matrix(s)
    solution = nearest_neighbor(s, matrix)
    result = evaluate(s, matrix, solution)
    assert result["feasible"] and result["vehicles_used"] == 2
    assert result["average_load_pct"] == pytest.approx(4 / 6 * 100)
    assert result["served_orders"] == 4


def test_capacity_shortage_not_proven_infeasible():
    s = scenario((4,), capacity=3)
    solution = nearest_neighbor(s, haversine_matrix(s))
    assert solution.status == "not_found"
    assert "not proven" in solution.message
    metrics = evaluate(s, haversine_matrix(s), solution)
    assert not metrics["feasible"] and metrics["distance_km"] is None


@pytest.mark.parametrize("routes,violation", [
    ([["D", "O0", "D"]], "missing_orders"),
    ([["D", "O0", "O1", "O1", "D"]], "duplicate_orders"),
    ([["D", "O0", "O1", "D"]], "capacity"),
    ([["O0", "O1", "D"]], "depot"),
    ([["D", "O0", "D", "O1", "D"]], "depot"),
    ([["D", "UNKNOWN", "D"]], "unknown_node"),
    ([["D", "D"]], "malformed"),
    ([["D", "O0", "D"], ["D", "O1", "D"]], "vehicle_limit"),
])
def test_independent_validation(routes, violation):
    s = scenario((2, 2), capacity=3, vehicles=1)
    metrics = evaluate(s, haversine_matrix(s), Solution("untrusted", routes))
    assert not metrics["feasible"]
    assert any(violation in e for e in metrics["violations"])
    assert metrics["distance_km"] is None


def test_unreachable_is_not_zero():
    s = scenario((1,))
    matrix = custom_matrix(s, [[0, None], [1, 0]])
    metrics = evaluate(s, matrix, Solution("external", [["D", "O0", "D"]]))
    assert not metrics["feasible"] and "unreachable" in " ".join(metrics["violations"])
    assert nearest_neighbor(s, matrix).status == "not_found"


def test_directed_two_opt_does_not_use_symmetric_shortcut():
    s = scenario((1, 1, 1), capacity=3, vehicles=1)
    # Reversing O0,O1 has cheaper boundary edges but a costly internal reverse edge.
    matrix = custom_matrix(s, [[0, 1, 0, 50], [50, 0, 1, 0],
                               [50, 100, 0, 1], [1, 50, 50, 0]])
    initial = Solution("external", [["D", "O0", "O1", "O2", "D"]])
    improved = two_opt(s, matrix, initial)
    assert evaluate(s, matrix, improved)["feasible"]
    assert route_cost(improved.routes[0], matrix) <= 4


@pytest.mark.parametrize("seed", range(10))
def test_two_opt_never_worsens_random_directed_instances(seed):
    rng = random.Random(seed)
    s = scenario((1,) * 12, capacity=4, vehicles=3)
    n = len(s.stops)
    matrix = custom_matrix(s, [[0 if i == j else rng.randint(1, 500) for j in range(n)]
                               for i in range(n)])
    initial = nearest_neighbor(s, matrix)
    improved = two_opt(s, matrix, initial)
    before, after = evaluate(s, matrix, initial), evaluate(s, matrix, improved)
    assert before["feasible"] and after["feasible"]
    assert after["distance_km"] <= before["distance_km"] + 1e-9
    assert sorted(sorted(r[1:-1]) for r in initial.routes) == sorted(
        sorted(r[1:-1]) for r in improved.routes)


def test_two_opt_rejects_infeasible_initial():
    s = scenario()
    result = two_opt(s, haversine_matrix(s), Solution("external", []))
    assert result.status == "not_found"


def test_known_crossing_route_improves():
    s = Scenario("square", Stop("D", 0, 0), (
        Stop("A", 0, 1, 1), Stop("B", 1, 0, 1), Stop("C", 1, 1, 1)), 1, 3)
    m = haversine_matrix(s)
    initial = Solution("external", [["D", "A", "B", "C", "D"]])
    improved = two_opt(s, m, initial)
    assert route_cost(improved.routes[0], m) < route_cost(initial.routes[0], m)
    assert initial.routes == [["D", "A", "B", "C", "D"]]  # No mutation of baseline.


def test_empty_instance_and_undefined_improvement():
    s = scenario(())
    result = evaluate(s, haversine_matrix(s), nearest_neighbor(s, haversine_matrix(s)))
    assert result["feasible"] and result["distance_km"] == 0
    assert improvement_pct(result, result) is None


def test_result_round_trip_and_tamper_detection(tmp_path):
    s = scenario()
    result = compare(s, haversine_matrix(s), repeat=3)
    target = tmp_path / "result.json"
    write_json(target, result)
    loaded = read_json(target)
    validate_experiment(loaded)
    assert len(loaded["runs"][0]["timing_repeats_s"]) == 3
    loaded["runs"][0]["metrics"]["distance_km"] = 0
    with pytest.raises(ValueError, match="metrics"):
        validate_experiment(loaded)


def test_input_fingerprint_tamper():
    s = scenario()
    result = compare(s, haversine_matrix(s))
    result["scenario"]["capacity"] = 100
    with pytest.raises(ValueError, match="fingerprint"):
        validate_experiment(result)


def test_public_export_whitelist():
    s = scenario()
    matrix = haversine_matrix(s)
    matrix.provenance["private_path"] = "private-value-do-not-copy"
    result = compare(s, matrix)
    result["private_secret"] = "private-value-do-not-copy"
    with pytest.raises(ValueError, match="review"):
        public_result(result)
    public = public_result(result, approved=True)
    assert "private-value-do-not-copy" not in json.dumps(public)
    assert "distances_m" not in json.dumps(public)
    assert public["data_mode"] == "precomputed"
    assert geojson(result)["features"][0]["geometry"]["coordinates"][0] == [0, 0]


def test_nonfinite_input_and_oversize(tmp_path):
    target = tmp_path / "bad.json"
    target.write_text('{"bad": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="finite"):
        read_json(target)
    with target.open("wb") as stream:
        stream.truncate(16 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="16 MiB"):
        read_json(target)


def test_cli_workflow_and_errors(tmp_path):
    result = tmp_path / "run.json"
    public = tmp_path / "public.json"
    assert main(["demo", "--out", str(result)]) == 0
    assert main(["export", "--input", str(result), "--format", "public",
                 "--out", str(public)]) == 2
    assert main(["export", "--input", str(result), "--format", "public",
                 "--out", str(public), "--approved-public-data"]) == 0
    assert read_json(public)["orders_count"] == 24
    s = tmp_path / "scenario.json"
    write_json(s, scenario().to_dict())
    assert main(["compare", "--scenario", str(s), "--out", str(result),
                 "--repeat", "0"]) == 2


def test_unknown_solver_rejected():
    s = scenario()
    with pytest.raises(ValueError):
        compare(s, haversine_matrix(s), ["typo"])


def test_improvement_tampering_rejected():
    s = scenario()
    result = compare(s, haversine_matrix(s))
    result["runs"][1]["improvement_pct"] = 99.99
    with pytest.raises(ValueError, match="improvement"):
        validate_experiment(result)


def test_skipped_solver_not_feasible_for_empty_problem():
    s = scenario(())
    result = evaluate(s, haversine_matrix(s), Solution("ortools", [], "skipped"))
    assert not result["feasible"]
