"""Optional adapter: no import-time dependency, no order dropping."""
import time
from importlib.metadata import version

from .evaluate import evaluate
from .models import Matrix, Scenario
from .solver import Solution


def solve_ortools(scenario: Scenario, matrix: Matrix, time_limit_s=3) -> Solution:
    matrix.validate_for(scenario)
    if not isinstance(time_limit_s, int) or not 1 <= time_limit_s <= 30:
        raise ValueError("OR-Tools time limit must be 1..30 seconds")
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    except ImportError:
        return Solution("ortools", [], "skipped", message="Install routeopt-study[ortools].")
    if any(s.demand != int(s.demand) for s in scenario.stops) or scenario.capacity != int(scenario.capacity):
        return Solution("ortools", [], "unsupported", message="OR-Tools adapter requires integer items.")
    start = time.perf_counter()
    manager = pywrapcp.RoutingIndexManager(len(scenario.stops), scenario.max_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)
    def transit(a, b):
        value = matrix.distances_m[manager.IndexToNode(a)][manager.IndexToNode(b)]
        return 0 if value is None else round(value)
    transit_id = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_id)
    demand_id = routing.RegisterUnaryTransitCallback(
        lambda a: int(scenario.stops[manager.IndexToNode(a)].demand))
    routing.AddDimensionWithVehicleCapacity(
        demand_id, 0, [int(scenario.capacity)] * scenario.max_vehicles, True, "Capacity")
    for a in range(routing.Size()):
        for b in range(routing.Size()):
            if matrix.distances_m[manager.IndexToNode(a)][manager.IndexToNode(b)] is None:
                routing.NextVar(a).RemoveValue(b)
        for vehicle in range(scenario.max_vehicles):
            end = routing.End(vehicle)
            if matrix.distances_m[manager.IndexToNode(a)][0] is None:
                routing.NextVar(a).RemoveValue(end)
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = time_limit_s
    assignment = routing.SolveWithParameters(params)
    routes = []
    if assignment:
        for vehicle in range(scenario.max_vehicles):
            index = routing.Start(vehicle)
            route = []
            while not routing.IsEnd(index):
                route.append(scenario.stops[manager.IndexToNode(index)].node_id)
                index = assignment.Value(routing.NextVar(index))
            route.append(scenario.depot.node_id)
            if len(route) > 2:
                routes.append(route)
    result = Solution("ortools", routes, "feasible" if assignment else "not_found",
                      time.perf_counter() - start,
                      {"time_limit_s": time_limit_s, "version": version("ortools"),
                       "distance_rounding": "nearest_meter",
                       "random_seed": "not_explicitly_configured",
                       "routing_status": int(routing.status())})
    if not evaluate(scenario, matrix, result)["feasible"]:
        result.status = "not_found"
    return result
