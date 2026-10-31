"""A solver-independent feasibility validator and metric calculator."""
from collections import Counter
import math

from .models import Matrix, Scenario
from .solver import Solution, route_cost


def evaluate(scenario: Scenario, matrix: Matrix, solution: Solution) -> dict:
    matrix.validate_for(scenario)
    depot = scenario.depot.node_id
    demands = {s.node_id: s.demand for s in scenario.orders}
    known = set(matrix.node_ids)
    seen, loads, errors = [], [], []
    if solution.status != "feasible":
        errors.append(f"solver_status:{solution.status}")
    if len(solution.routes) > scenario.max_vehicles:
        errors.append("vehicle_limit")
    total = 0.0
    for index, route in enumerate(solution.routes):
        if not isinstance(route, list) or len(route) < 3:
            errors.append(f"route_{index}:empty_or_malformed")
            continue
        if route[0] != depot or route[-1] != depot or depot in route[1:-1]:
            errors.append(f"route_{index}:depot")
        if any(node not in known for node in route):
            errors.append(f"route_{index}:unknown_node")
        interiors = route[1:-1]
        seen.extend(node for node in interiors if node in demands)
        load = sum(demands.get(node, 0) for node in interiors)
        loads.append(load)
        if load > scenario.capacity + 1e-9:
            errors.append(f"route_{index}:capacity")
        if all(node in known for node in route):
            cost = route_cost(route, matrix)
            if not math.isfinite(cost):
                errors.append(f"route_{index}:unreachable")
            else:
                total += cost
    count = Counter(seen)
    if set(demands) - set(count):
        errors.append("missing_orders")
    if any(v > 1 for v in count.values()):
        errors.append("duplicate_orders")
    feasible = not errors
    used = len(solution.routes)
    return {"feasible": feasible, "violations": errors,
            "distance_km": total / 1000 if feasible else None,
            "vehicles_used": used if feasible else None,
            "average_load_pct": (sum(loads) / (used * scenario.capacity) * 100
                                 if used else 0.0) if feasible else None,
            "served_orders": sum(count.values()), "orders_total": len(demands),
            "solver_elapsed_s": solution.elapsed_s}


def improvement_pct(baseline: dict, candidate: dict) -> float | None:
    if not baseline["feasible"] or not candidate["feasible"] or baseline["distance_km"] <= 0:
        return None
    return (baseline["distance_km"] - candidate["distance_km"]) / baseline["distance_km"] * 100
