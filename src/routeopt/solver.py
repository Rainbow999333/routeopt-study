"""Capacity-constrained nearest neighbor and directed-safe route-local 2-opt."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import time

from .models import Matrix, Scenario


@dataclass
class Solution:
    solver: str
    routes: list[list[str]]
    status: str = "feasible"
    elapsed_s: float = 0
    parameters: dict = field(default_factory=dict)
    message: str = ""


def route_cost(route: list[str], matrix: Matrix) -> float:
    positions = {node_id: i for i, node_id in enumerate(matrix.node_ids)}
    cost = 0.0
    for a, b in zip(route, route[1:]):
        value = matrix.distances_m[positions[a]][positions[b]]
        if value is None:
            return math.inf
        cost += value
    return cost


def nearest_neighbor(scenario: Scenario, matrix: Matrix) -> Solution:
    matrix.validate_for(scenario)
    start = time.perf_counter()
    positions = {node_id: i for i, node_id in enumerate(matrix.node_ids)}
    remaining = {s.node_id: s for s in scenario.orders}
    depot = scenario.depot.node_id
    routes = []
    while remaining and len(routes) < scenario.max_vehicles:
        route, load = [depot], 0.0
        while remaining:
            candidates = []
            for stop in remaining.values():
                a, b = positions[route[-1]], positions[stop.node_id]
                distance = matrix.distances_m[a][b]
                if (load + stop.demand <= scenario.capacity + 1e-9
                        and distance is not None and matrix.distances_m[b][0] is not None):
                    candidates.append((distance, stop.node_id))
            if not candidates:
                break
            _, chosen = min(candidates)
            load += remaining.pop(chosen).demand
            route.append(chosen)
        if len(route) == 1:
            break
        routes.append(route + [depot])
    return Solution("nn", routes, "not_found" if remaining else "feasible",
                    time.perf_counter() - start,
                    {"tie_break": "distance_then_node_id", "seed": 0},
                    "Greedy construction did not serve every order; infeasibility is not proven."
                    if remaining else "")


def two_opt(scenario: Scenario, matrix: Matrix, initial: Solution | None = None,
            time_limit_s: float = 2.0, max_passes: int = 50) -> Solution:
    matrix.validate_for(scenario)
    if not math.isfinite(time_limit_s) or not 0 < time_limit_s <= 60:
        raise ValueError("2-opt time_limit_s must be in (0, 60]")
    if not isinstance(max_passes, int) or not 1 <= max_passes <= 1000:
        raise ValueError("2-opt max_passes must be in 1..1000")
    start = time.perf_counter()
    if initial is None:
        initial = nearest_neighbor(scenario, matrix)
    from .evaluate import evaluate
    if not evaluate(scenario, matrix, initial)["feasible"]:
        return Solution("2opt", [r[:] for r in initial.routes], "not_found",
                        time.perf_counter() - start, message="No feasible initial solution.")
    routes = [r[:] for r in initial.routes]
    passes, timed_out = 0, False
    for _ in range(max_passes):
        improved = False
        passes += 1
        for route in routes:
            current_cost = route_cost(route, matrix)
            for i in range(1, len(route) - 2):
                for j in range(i + 1, len(route) - 1):
                    if time.perf_counter() - start >= time_limit_s:
                        timed_out = True
                        break
                    candidate = route[:i] + list(reversed(route[i:j + 1])) + route[j + 1:]
                    # Full directed cost includes every internal edge reversed by the move.
                    candidate_cost = route_cost(candidate, matrix)
                    if candidate_cost < current_cost - 1e-8:
                        route[:] = candidate
                        current_cost = candidate_cost
                        improved = True
                if timed_out:
                    break
            if timed_out:
                break
        if timed_out or not improved:
            break
    return Solution("2opt", routes, "feasible", time.perf_counter() - start,
                    {"seed": 0, "time_limit_s": time_limit_s, "max_passes": max_passes,
                     "passes": passes, "limit_reached": timed_out,
                     "initial_solver": initial.solver,
                     "construction_elapsed_s": initial.elapsed_s,
                     "neighborhood": "intra_route_directed_reversal"})
