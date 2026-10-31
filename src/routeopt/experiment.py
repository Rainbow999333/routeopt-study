from dataclasses import asdict
from datetime import datetime, timezone
import platform
import statistics

from . import __version__
from .evaluate import evaluate, improvement_pct
from .models import Matrix, Scenario, SCHEMA_VERSION, fingerprint
from .solver import nearest_neighbor, two_opt


def compare(scenario: Scenario, matrix: Matrix, solvers=("nn", "2opt"), repeat=1) -> dict:
    if not isinstance(repeat, int) or not 1 <= repeat <= 20:
        raise ValueError("repeat must be in 1..20")
    if not solvers or set(solvers) - {"nn", "2opt", "ortools"} or len(set(solvers)) != len(solvers):
        raise ValueError("choose distinct solvers from nn,2opt,ortools")
    matrix.validate_for(scenario)
    runs = []
    for solver in solvers:
        solutions = []
        for _ in range(repeat):
            if solver == "nn":
                solution = nearest_neighbor(scenario, matrix)
            elif solver == "2opt":
                solution = two_opt(scenario, matrix)
            else:
                from .optional_ortools import solve_ortools
                solution = solve_ortools(scenario, matrix)
            solutions.append(solution)
        # Repeat the fixed algorithm; choose the FIRST result, never cherry-pick the best.
        solution = solutions[0]
        metrics = evaluate(scenario, matrix, solution)
        runs.append({"solver": solver, **asdict(solution), "metrics": metrics,
                     "timing_repeats_s": [s.elapsed_s for s in solutions],
                     "median_elapsed_s": statistics.median(s.elapsed_s for s in solutions)})
    baseline = next((r["metrics"] for r in runs if r["solver"] == "nn"), None)
    for run in runs:
        run["improvement_pct"] = improvement_pct(baseline, run["metrics"]) if baseline else None
    created = datetime.now(timezone.utc).isoformat()
    inputs = {"scenario": scenario.to_dict(), "matrix": matrix.to_dict()}
    return {"schema_version": SCHEMA_VERSION,
            "run_id": fingerprint({"inputs": inputs, "created_at": created, "solvers": solvers})[:20],
            "created_at": created, "scenario_sha256": scenario.digest,
            "matrix_sha256": matrix.digest, "environment": {"routeopt": __version__,
            "python": platform.python_version(), "platform": platform.system()},
            **inputs, "runs": runs}


def markdown_report(experiment: dict) -> str:
    lines = ["# Route optimization comparison", "",
             f"Scenario: {experiment['scenario']['scenario_id']}",
             f"Matrix: {experiment['matrix']['provenance']['provider']}", "",
             "| Algorithm | Status | Feasible | km | Vehicles | Load % | Solve s | Improvement % |",
             "|---|---|---|---:|---:|---:|---:|---:|"]
    def fmt(value):
        return "N/A" if value is None else f"{value:.3f}"
    for run in experiment["runs"]:
        m = run["metrics"]
        lines.append(f"| {run['solver']} | {run['status']} | {m['feasible']} | "
                     f"{fmt(m['distance_km'])} | {m['vehicles_used']} | "
                     f"{fmt(m['average_load_pct'])} | {fmt(m['solver_elapsed_s'])} | "
                     f"{fmt(run['improvement_pct'])} |")
    return "\n".join(lines) + "\n"
