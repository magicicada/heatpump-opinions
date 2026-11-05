#!/usr/bin/env python3
"""Entry point: run the heat pump adoption simulation and produce the
motivation and ownership animation described in settings.yaml.

Each run writes to its own subdirectory of `output.results_dir`, named after
the world it ran on (or `--run-name`), so runs on different worlds sit side
by side instead of overwriting each other.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from heatpump_sim.metrics import summarise
from heatpump_sim.network import expected_cross_cell_share, kernel_params, summarise_network
from heatpump_sim.settings import Settings
from heatpump_sim.simulate import run_simulation, save_results
from heatpump_sim.visualize import animate


def default_run_name(settings: Settings) -> str:
    """Name the run after the world it uses, so results are self-identifying."""
    if settings.get("households.location_source", "generate") == "file":
        source = settings.get("households.households_source_file")
        if source:
            return Path(source).stem
    return "generated"


def network_summary(settings: Settings, result) -> dict:
    """Structure of the network the run used, including the share of ties
    crossing an LSOA-like cell boundary when the world records cells."""
    params = settings.get("network.params", {}) or {}
    spatial = settings.get("network.type", "spatial_kernel") == "spatial_kernel"
    metres_per_unit = kernel_params(params)["metres_per_unit"] if spatial else None
    cell_ids = result.attributes.get("lsoa_id")
    summary = summarise_network(result.graph, result.locations, cell_ids, metres_per_unit)
    if spatial and cell_ids is not None:
        summary["expected_cross_cell_share"] = expected_cross_cell_share(
            result.locations, cell_ids, params
        )
    return summary


def write_run_info(path: Path, settings: Settings, result, run_name: str) -> None:
    """Record what produced this run, so a results directory found later can
    be traced back to its inputs."""
    info = {
        "run_name": run_name,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "world": {
            "location_source": settings.get("households.location_source"),
            "world_file": settings.get("households.households_source_file"),
            "n_households": int(len(result.locations)),
        },
        "simulation": settings.get("simulation", {}),
        "adoption": settings.get("adoption", {}),
        "motivation": settings.get("motivation", {}),
        "word_of_mouth": settings.get("word_of_mouth", {}),
        "dissatisfaction": settings.get("dissatisfaction", {}),
        "network": settings.get("network", {}),
        "network_summary": network_summary(settings, result),
        "outcome": summarise(result.history, result.attributes.get("lsoa_archetype")),
    }
    with open(path, "w") as f:
        json.dump(info, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", default="settings.yaml", help="Path to settings YAML file")
    parser.add_argument("--run-name", default=None,
                        help="Subdirectory name for this run's results (default: the world file's name)")
    parser.add_argument("--world", default=None,
                        help="World file to run on, overriding households.households_source_file")
    parser.add_argument("--seed", type=int, default=None, help="Override simulation.random_seed")
    parser.add_argument("--no-animations", action="store_true",
                        help="Skip GIF rendering, which dominates runtime")
    args = parser.parse_args()

    settings = Settings.load(args.settings)

    if args.world is not None:
        settings.raw.setdefault("households", {})["location_source"] = "file"
        settings.raw["households"]["households_source_file"] = args.world
    if args.seed is not None:
        settings.raw.setdefault("simulation", {})["random_seed"] = args.seed

    run_name = args.run_name or default_run_name(settings)
    results_dir = Path(settings.get("output.results_dir", "results")) / run_name

    print(f"Running simulation (run: {run_name})...")
    result = run_simulation(settings)

    save_results(result, results_dir)
    write_run_info(results_dir / "run_info.json", settings, result, run_name)
    print(f"Saved raw history to {results_dir / 'history.npz'}")

    if not args.no_animations:
        out = results_dir / settings.get("output.animation", "adoption_animation.gif")
        print(f"Rendering animation to {out}...")
        animate(result, out, fps=settings.get("output.fps", 8),
                every_months=settings.get("output.animation_every_months", 3))

    h = result.history
    months = len(h.owner) - 1
    print(f"Done. After {months} months ({months / 12:g} years): "
          f"{h.owner[-1].sum()}/{len(result.locations)} households own a heat pump, "
          f"{h.dissatisfied[-1].sum()} of them dissatisfied")
    print(f"Results in {results_dir}/")


if __name__ == "__main__":
    main()
