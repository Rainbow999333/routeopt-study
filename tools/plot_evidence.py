"""Publication figures from the same verified experiment records used by the website."""
import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from routeopt.export import validate_experiment
from routeopt.io import read_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiments", type=Path, default=Path("experiments/chongqing-2026-11-01"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    cases = [(key, read_json(args.experiments / key / "result.json")) for key in
             ("standard", "small-vehicle", "large-vehicle", "higher-demand")]
    for _, result in cases:
        validate_experiment(result)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#a4b0a2", "axes.labelcolor": "#34443e",
                         "text.color": "#173a34", "xtick.color": "#5d6d62",
                         "ytick.color": "#5d6d62", "figure.facecolor": "#fffefa",
                         "axes.facecolor": "#fffefa", "svg.hashsalt": "routeopt-v1"})
    fig, ax = plt.subplots(figsize=(10, 5.8))
    x = range(4)
    baseline = [result["runs"][0]["metrics"]["distance_km"] for _, result in cases]
    optimized = [result["runs"][1]["metrics"]["distance_km"] for _, result in cases]
    a = ax.bar([i - .19 for i in x], baseline, width=.36, label="Capacity-aware NN", color="#bc7656")
    b = ax.bar([i + .19 for i in x], optimized, width=.36, label="NN + directed 2-opt", color="#176854")
    ax.bar_label(a, fmt="%.3f", padding=4, fontsize=9)
    ax.bar_label(b, fmt="%.3f", padding=4, fontsize=9)
    ax.set_xticks(list(x), ["Standard\n50 items/vehicle", "Small vehicles\n35 items/vehicle",
                           "Large vehicles\n70 items/vehicle", "Higher demand\n50 items/vehicle"])
    ax.set_ylim(0, 112)
    ax.set_ylabel("Total distance (km)")
    ax.set_title("Four scenarios. One fixed road matrix.", loc="left", fontsize=18, pad=24)
    ax.yaxis.grid(True, color="#e4e8df")
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left", ncols=2)
    fig.text(.1, .025, "24 public road nodes + 1 simulated depot. Demand and fleet are simulated.\n"
             "© OpenStreetMap contributors · ODbL. Static OSRM car snapshot; not field delivery results.",
             fontsize=8, color="#5d6d62")
    fig.subplots_adjust(bottom=.2, top=.84, left=.1, right=.97)
    for extension in ("png", "svg"):
        fig.savefig(args.out / ("scenario-comparison." + extension), dpi=200)
    plt.close(fig)

    geometry = read_json(root / "data/chongqing/road-geometry.json")
    roads = json.loads((root / "web/data/roads.json").read_text(encoding="utf-8"))["roads"]
    result = cases[0][1]
    lat = sum(s["lat"] for s in result["scenario"]["orders"]) / 24
    coslat = math.cos(math.radians(lat))
    def project(points):
        return [(p[0] * coslat, p[1]) for p in points]
    def route_line(route):
        points = []
        for a, b in zip(route, route[1:]):
            points.extend(geometry["arcs"][a + ">" + b]["coordinates"])
        return project(points)
    all_points = [p for run in result["runs"] for route in run["routes"] for p in route_line(route)]
    xmin, xmax = min(p[0] for p in all_points), max(p[0] for p in all_points)
    ymin, ymax = min(p[1] for p in all_points), max(p[1] for p in all_points)
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.7), sharex=True, sharey=True)
    for ax, run, color in zip(axes, result["runs"], ["#b84b2d", "#176854"]):
        ax.add_collection(LineCollection([project(road) for road in roads], colors="#d7dfd1", linewidths=.6))
        ax.add_collection(LineCollection([route_line(route) for route in run["routes"]],
                                        colors=color, linewidths=1.6))
        nodes = result["scenario"]["orders"]
        ax.scatter([p["lng"] * coslat for p in nodes], [p["lat"] for p in nodes], s=13,
                   facecolor="#fffefa", edgecolor="#365f51", linewidth=.7, zorder=3)
        depot = result["scenario"]["depot"]
        ax.scatter(depot["lng"] * coslat, depot["lat"], marker="s", s=45, color="#173a34", zorder=4)
        ax.set_xlim(xmin - .002, xmax + .002)
        ax.set_ylim(ymin - .002, ymax + .002)
        ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values(): spine.set_visible(False)
        ax.set_title(("Nearest neighbor" if run["solver"] == "nn" else "NN + directed 2-opt") +
                     f"\n{run['metrics']['distance_km']:.3f} km · {run['metrics']['vehicles_used']} vehicles",
                     loc="left", fontsize=13, pad=15)
    fig.suptitle("Chongqing Nan'an: change the order, keep the constraints", fontsize=17, y=.97)
    fig.text(.04, .045, "Same 24 nodes, demand, capacity and matrix. Square: simulated depot. "
             "No live traffic, time windows or field validation.\n"
             "© OpenStreetMap contributors · ODbL. Geometry checked against matrix arcs.", fontsize=8, color="#5d6d62")
    fig.subplots_adjust(left=.04, right=.96, top=.82, bottom=.12, wspace=.09)
    for extension in ("png", "svg"):
        fig.savefig(args.out / ("standard-route-comparison." + extension), dpi=200)
    plt.close(fig)
    print(json.dumps({"figures": 4, "output_directory": str(args.out)}))


if __name__ == "__main__":
    main()
