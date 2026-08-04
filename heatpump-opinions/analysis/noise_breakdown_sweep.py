#!/usr/bin/env python3
"""Sweep opinions.noise_std x heatpumps.breakdown_rate and record how far
adoption gets after 100 timesteps, averaged over several random seeds.

Answers: how much opinion noise is needed to get adoption moving, and how
does that requirement shift as heat pump breakdowns become more common?
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from heatpump_sim.settings import Settings
from heatpump_sim.simulate import run_simulation

BASE_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.yaml"
N_SEEDS = 8
SEEDS = list(range(N_SEEDS))

BREAKDOWN_RATES = [0.0, 0.005, 0.01, 0.02, 0.05, 0.10]
NOISE_STDS = [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20]


def final_adoption_fraction(breakdown_rate: float, noise_std: float, seed: int, base: dict) -> float:
    cfg = copy.deepcopy(base)
    cfg["heatpumps"]["breakdown_rate"] = breakdown_rate
    cfg["opinions"]["noise_std"] = noise_std
    cfg["simulation"]["random_seed"] = seed
    settings = Settings(cfg)
    result = run_simulation(settings)
    return result.heatpump_history[-1].sum() / len(result.locations)


def main() -> None:
    base = yaml.safe_load(open(BASE_SETTINGS_PATH))

    results = np.zeros((len(BREAKDOWN_RATES), len(NOISE_STDS)))
    for i, br in enumerate(BREAKDOWN_RATES):
        for j, noise in enumerate(NOISE_STDS):
            fracs = [final_adoption_fraction(br, noise, seed, base) for seed in SEEDS]
            results[i, j] = np.mean(fracs)
            print(f"breakdown_rate={br:<6} noise_std={noise:<5} mean_final_adoption={results[i, j]:.3f}")

    out_dir = Path(__file__).resolve().parent
    np.savez(out_dir / "sweep_results.npz",
             breakdown_rates=BREAKDOWN_RATES, noise_stds=NOISE_STDS, adoption=results)

    # Minimum noise_std (from the tested grid) at which mean adoption clears 0.5 of households.
    print("\nApprox. minimum noise_std tested for >50% adoption by t=100:")
    for i, br in enumerate(BREAKDOWN_RATES):
        row = results[i]
        above = np.where(row > 0.5)[0]
        min_noise = NOISE_STDS[above[0]] if len(above) else None
        print(f"  breakdown_rate={br:<6}: {min_noise}")


if __name__ == "__main__":
    main()
