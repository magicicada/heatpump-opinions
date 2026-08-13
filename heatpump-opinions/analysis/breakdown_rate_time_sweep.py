#!/usr/bin/env python3
"""How does the heat pump breakdown rate affect how quickly adoption
spreads? Sweeps heatpumps.breakdown_rate, holding every other setting at
its settings.yaml value, and tracks the full adoption-fraction-over-time
curve (averaged over several seeds) for each rate.

Runs longer than the default 100 steps (see HORIZON below) so that slower,
higher-breakdown scenarios have a fair chance to reach the adoption
thresholds we're timing instead of being cut off mid-climb.
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
HORIZON = 300
N_SEEDS = 10
SEEDS = list(range(N_SEEDS))
BREAKDOWN_RATES = [0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.10]
THRESHOLDS = [0.20, 0.50, 0.90]


def adoption_curve(breakdown_rate: float, seed: int, base: dict) -> np.ndarray:
    cfg = copy.deepcopy(base)
    cfg["heatpumps"]["breakdown_rate"] = breakdown_rate
    cfg["simulation"]["num_timesteps"] = HORIZON
    cfg["simulation"]["random_seed"] = seed
    settings = Settings(cfg)
    result = run_simulation(settings)
    return result.heatpump_history.mean(axis=1)  # adoption fraction per timestep


def time_to_threshold(mean_curve: np.ndarray, threshold: float) -> float | None:
    above = np.where(mean_curve >= threshold)[0]
    if len(above) == 0:
        return None
    t = above[0]
    if t == 0:
        return 0.0
    # linear interpolation between t-1 and t for a smoother estimate
    y0, y1 = mean_curve[t - 1], mean_curve[t]
    frac = (threshold - y0) / (y1 - y0) if y1 != y0 else 0.0
    return (t - 1) + frac


def main() -> None:
    base = yaml.safe_load(open(BASE_SETTINGS_PATH))

    curves = np.zeros((len(BREAKDOWN_RATES), HORIZON + 1))
    for i, br in enumerate(BREAKDOWN_RATES):
        seed_curves = np.array([adoption_curve(br, seed, base) for seed in SEEDS])
        curves[i] = seed_curves.mean(axis=0)
        print(f"breakdown_rate={br:<6} final_adoption(t={HORIZON})={curves[i, -1]:.3f}")

    out_dir = Path(__file__).resolve().parent
    np.savez(out_dir / "breakdown_time_sweep_results.npz",
             breakdown_rates=BREAKDOWN_RATES, curves=curves, horizon=HORIZON)

    print("\nTime to reach adoption thresholds (mean over seeds, linear-interpolated; '-' = not reached by t=%d):" % HORIZON)
    header = "breakdown_rate  " + "  ".join(f"t@{int(th*100)}%" for th in THRESHOLDS)
    print(header)
    for i, br in enumerate(BREAKDOWN_RATES):
        row = [time_to_threshold(curves[i], th) for th in THRESHOLDS]
        row_str = "  ".join(f"{t:6.1f}" if t is not None else "     -" for t in row)
        print(f"{br:<16}{row_str}")


if __name__ == "__main__":
    main()
