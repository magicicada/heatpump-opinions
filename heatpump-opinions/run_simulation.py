#!/usr/bin/env python3
"""Entry point: run the heat pump adoption simulation and produce the
opinion and heat-pump-adoption animations described in settings.yaml."""
from __future__ import annotations

import argparse
from pathlib import Path

from heatpump_sim.settings import Settings
from heatpump_sim.simulate import run_simulation, save_results
from heatpump_sim.visualize import animate_combined, animate_heatpumps, animate_opinions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", default="settings.yaml", help="Path to settings YAML file")
    args = parser.parse_args()

    settings = Settings.load(args.settings)

    print("Running simulation...")
    result = run_simulation(settings)

    results_dir = Path(settings.get("output.results_dir", "results"))
    save_results(result, results_dir)
    print(f"Saved raw history to {results_dir / 'history.npz'}")

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
    print(f"Done. Final heat pump ownership: {n_final_installed}/{len(result.locations)}; breakdowns so far: {n_broken}")


if __name__ == "__main__":
    main()
