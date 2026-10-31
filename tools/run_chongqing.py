"""Run a predefined scenario set against one fixed road matrix, without tuning for wins."""
import argparse
from dataclasses import replace
from pathlib import Path

from routeopt.experiment import compare, markdown_report
from routeopt.export import public_result
from routeopt.io import read_json, write_json
from routeopt.models import Matrix, Scenario


SCENARIOS = [
    ("standard", "标准车队", 5, 50, 1.0),
    ("small-vehicle", "小容量车辆", 6, 35, 1.0),
    ("large-vehicle", "大容量车辆", 4, 70, 1.0),
    ("higher-demand", "较高需求", 6, 50, 1.3),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--solvers", default="nn,2opt")
    args = parser.parse_args()
    if any((args.out / key / "result.json").exists() for key, *_ in SCENARIOS):
        raise ValueError("saved experiments exist; choose a new output directory")
    original = Scenario.from_dict(read_json(args.input / "scenario.json"))
    matrix = Matrix.from_dict(read_json(args.input / "matrix.json"))
    outputs = []
    for suffix, label, vehicles, capacity, factor in SCENARIOS:
        scenario = replace(original, scenario_id=original.scenario_id + "-" + suffix,
                           max_vehicles=vehicles, capacity=capacity,
                           orders=tuple(replace(stop, demand=round(stop.demand * factor))
                                        for stop in original.orders),
                           description=f"{label}。需求逐单乘以 {factor} 后取整。{original.description}")
        result = compare(scenario, matrix, solvers=args.solvers.split(","), repeat=5)
        write_json(args.out / suffix / "result.json", result)
        (args.out / suffix / "comparison.md").write_text(markdown_report(result), encoding="utf-8")
        write_json(args.out / suffix / "public.json", public_result(result, approved=True))
        outputs.append({"scenario": suffix, "run_id": result["run_id"],
                        "feasible": [r["metrics"]["feasible"] for r in result["runs"]]})
        print(markdown_report(result))
    write_json(args.out / "index.json", {"scenarios": outputs})


if __name__ == "__main__":
    main()
