"""Exports revalidate results and copy only explicitly public fields."""
from .evaluate import evaluate, improvement_pct
from .models import Matrix, Scenario, SCHEMA_VERSION, number
from .solver import Solution


def validate_experiment(experiment):
    if experiment.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported result schema_version")
    scenario = Scenario.from_dict(experiment["scenario"])
    matrix = Matrix.from_dict(experiment["matrix"])
    matrix.validate_for(scenario)
    if scenario.digest != experiment["scenario_sha256"] or matrix.digest != experiment["matrix_sha256"]:
        raise ValueError("experiment input fingerprint mismatch")
    labels = [r["solver"] for r in experiment["runs"]]
    if not labels or len(set(labels)) != len(labels) or set(labels) - {"nn", "2opt", "ortools"}:
        raise ValueError("invalid or duplicate solver labels")
    for run in experiment["runs"]:
        number(run["elapsed_s"], "elapsed_s")
        solution = Solution(run["solver"], run["routes"], run["status"], run["elapsed_s"])
        actual = evaluate(scenario, matrix, solution)
        if actual != run["metrics"]:
            raise ValueError("stored result metrics do not match independently recalculated metrics")
    baseline = next((r["metrics"] for r in experiment["runs"] if r["solver"] == "nn"), None)
    for run in experiment["runs"]:
        actual = improvement_pct(baseline, run["metrics"]) if baseline else None
        if actual != run["improvement_pct"]:
            raise ValueError("stored improvement does not match recalculated improvement")
    return scenario, matrix


def geojson(experiment: dict) -> dict:
    scenario, _ = validate_experiment(experiment)
    stops = {s.node_id: s for s in scenario.stops}
    features = []
    for run in experiment["runs"]:
        if not run["metrics"]["feasible"]:
            continue
        for index, route in enumerate(run["routes"]):
            features.append({"type": "Feature", "properties": {
                "solver": run["solver"], "vehicle": index + 1,
                "geometry_type": "visit_order_schematic",
                "description": "Straight connections; not road-following navigation geometry."},
                "geometry": {"type": "LineString",
                             "coordinates": [[stops[n].lng, stops[n].lat] for n in route]}})
    return {"type": "FeatureCollection", "features": features}


def public_result(experiment: dict, *, approved: bool = False) -> dict:
    if not approved:
        raise ValueError("public export requires an explicit approved=True data review")
    scenario, matrix = validate_experiment(experiment)
    # Provenance is whitelisted; arbitrary URLs, paths, tokens and metadata are not copied.
    provider = matrix.provenance["provider"]
    if provider not in {"haversine", "osrm", "osm_local_graph"}:
        raise ValueError("provider is not approved for public export")
    return {"schema_version": SCHEMA_VERSION, "scenario_id": scenario.scenario_id,
            "run_id": experiment["run_id"], "created_at": experiment["created_at"],
            "scenario_sha256": scenario.digest, "matrix_sha256": matrix.digest,
            "description": scenario.description, "coordinate_system": "WGS84",
            "data_mode": "precomputed", "provider": provider,
            "data_license": matrix.provenance.get("license"),
            "attribution": matrix.provenance.get("attribution"),
            "source_snapshot_sha256": matrix.provenance.get("osm_sha256"),
            "matrix_created_at": matrix.provenance.get("created_at"),
            "orders_count": len(scenario.orders), "max_vehicles": scenario.max_vehicles,
            "capacity": scenario.capacity, "demand_unit": "items",
            "stops": [{"node_id": s.node_id, "lat": s.lat, "lng": s.lng,
                       "demand": s.demand, "is_depot": s == scenario.depot} for s in scenario.stops],
            "runs": [{"solver": r["solver"], "status": r["status"],
                      "routes": r["routes"], "metrics": r["metrics"],
                      "improvement_pct": r["improvement_pct"]} for r in experiment["runs"]],
            "geometry": geojson(experiment)}
