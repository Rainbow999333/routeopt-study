import argparse
from importlib.resources import files
import json
from pathlib import Path
import sys

from .experiment import compare, markdown_report
from .export import geojson, public_result
from .io import read_json, write_json
from .matrix import haversine_matrix
from .models import Matrix, Scenario


def main(argv=None):
    parser = argparse.ArgumentParser(prog="routeopt", description="Reproducible offline delivery experiments")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Run the bundled synthetic, straight-line sample")
    demo.add_argument("--out", type=Path, default=Path("out/demo.json"))
    demo.add_argument("--solvers", default="nn,2opt")
    for name in ("solve", "compare"):
        command = sub.add_parser(name)
        command.add_argument("--scenario", type=Path, required=True)
        command.add_argument("--matrix", type=Path, help="Saved matrix JSON; defaults to Haversine")
        command.add_argument("--out", type=Path, required=True)
        if name == "solve":
            command.add_argument("--solver", choices=("nn", "2opt", "ortools"), default="2opt")
        else:
            command.add_argument("--solvers", default="nn,2opt")
            command.add_argument("--repeat", type=int, default=1)
    export = sub.add_parser("export")
    export.add_argument("--input", type=Path, required=True)
    export.add_argument("--format", choices=("geojson", "public", "markdown"), required=True)
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--approved-public-data", action="store_true",
                        help="Confirm that every exported field and its license were reviewed")
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            experiment = read_json(args.input)
            if args.format == "markdown":
                from .export import validate_experiment
                validate_experiment(experiment)
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(markdown_report(experiment), encoding="utf-8")
            else:
                result = geojson(experiment) if args.format == "geojson" else public_result(
                    experiment, approved=args.approved_public_data)
                write_json(args.out, result)
            print(f"Exported {args.format} to {args.out}")
            return 0
        if args.command == "demo":
            scenario = Scenario.from_dict(json.loads(
                files("routeopt").joinpath("samples/demo.json").read_text(encoding="utf-8")))
            matrix, solvers, repeat = haversine_matrix(scenario), args.solvers.split(","), 1
        else:
            scenario = Scenario.from_dict(read_json(args.scenario))
            matrix = Matrix.from_dict(read_json(args.matrix)) if args.matrix else haversine_matrix(scenario)
            solvers = [args.solver] if args.command == "solve" else args.solvers.split(",")
            repeat = 1 if args.command == "solve" else args.repeat
        experiment = compare(scenario, matrix, solvers=solvers, repeat=repeat)
        write_json(args.out, experiment)
        print(markdown_report(experiment))
        any_feasible = any(r["metrics"]["feasible"] for r in experiment["runs"])
        all_acceptable = all(r["metrics"]["feasible"] or r["status"] == "skipped"
                             for r in experiment["runs"])
        return 0 if any_feasible and all_acceptable else 2
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"routeopt: {exc}", file=sys.stderr)
        return 2
