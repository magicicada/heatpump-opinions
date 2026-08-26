#!/usr/bin/env python3
"""Entry point: run the heat pump adoption simulation and produce the
opinion and heat-pump-adoption animations described in settings.yaml.

Each run writes to its own subdirectory of `output.results_dir`, named after
the world it ran on (or `--run-name`), so runs on different worlds sit side
by side instead of overwriting each other.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from heatpump_sim.settings import Settings
from heatpump_sim.simulate import run_simulation, save_results
from heatpump_sim.visualize import animate_combined, animate_heatpumps, animate_opinions


def default_run_name(settings: Settings) -> str:
    """Name the run after the world it uses, so results are self-identifying."""
    if settings.get("households.location_source", "generate") == "file":
        source = settings.get("households.households_source_file")
        if source:
            return Path(source).stem
    return "generated"


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
        "simulation": {
            "random_seed": settings.get("simulation.random_seed"),
            "num_timesteps": settings.get("simulation.num_timesteps"),
        },
        "heatpumps": settings.get("heatpumps", {}),
        "opinions": settings.get("opinions", {}),
        "network": settings.get("network", {}),
        "outcome": {
            "final_adopted": int(result.heatpump_history[-1].sum()),
            "final_adoption_fraction": float(result.heatpump_history[-1].mean()),
            "total_broken_down": int(result.broken_history[-1].sum()),
        },
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
        fps = settings.get("output.fps", 8)

        opinion_out = results_dir / settings.get("output.opinion_animation", "opinion_animation.gif")
        print(f"Rendering opinion animation to {opinion_out}...")
        animate_opinions(result, opinion_out, fps=fps)

        heatpump_out = results_dir / settings.get("output.heatpump_animation", "heatpump_animation.gif")
        print(f"Rendering heat pump animation to {heatpump_out}...")
        animate_heatpumps(result, heatpump_out, fps=fps)

        combined_out = results_dir / settings.get("output.combined_animation", "combined_animation.gif")
        print(f"Rendering combined animation to {combined_out}...")
        animate_combined(result, combined_out, fps=fps)

    n_final_installed = result.heatpump_history[-1].sum()
    n_broken = result.broken_history[-1].sum()
    print(f"Done. Final heat pump ownership: {n_final_installed}/{len(result.locations)}; "
          f"breakdowns so far: {n_broken}")
    print(f"Results in {results_dir}/")


if __name__ == "__main__":
    main()
