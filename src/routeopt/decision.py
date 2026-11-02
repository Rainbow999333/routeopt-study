"""Translate independently validated routes into limited dispatch evidence."""
import math

from .export import validate_experiment


def decision_summary(result: dict) -> dict:
    """Return static driving durations; never infer cash savings or live ETAs."""
    _, matrix = validate_experiment(result)
    positions = {node: i for i, node in enumerate(matrix.node_ids)}
    runs = {}
    for run in result["runs"]:
        if not run["metrics"]["feasible"]:
            continue
        minutes = None
        if matrix.durations_s is not None:
            minutes = []
            for route in run["routes"]:
                durations = [matrix.durations_s[positions[a]][positions[b]] for a, b in zip(route, route[1:])]
                if any(value is None for value in durations):
                    minutes = None
                    break
                minutes.append(math.fsum(durations) / 60)
        runs[run["solver"]] = {
            "distance_km": run["metrics"]["distance_km"],
            "vehicles": run["metrics"]["vehicles_used"],
            "total_drive_minutes": math.fsum(minutes) if minutes is not None else None,
            "longest_drive_minutes": max(minutes, default=0) if minutes is not None else None,
        }
    return {"matrix_sha256": matrix.digest, "runs": runs,
            "duration_mode": "static_model_no_service_waiting_or_live_traffic",
            "cost_mode": "visitor_assumed_variable_cost_per_vehicle_km_excluding_labour_and_fixed_cost"}
