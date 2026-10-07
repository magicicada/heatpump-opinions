"""Jess's proposed fix, tried outside the model code: little or no opinion noise,
everyone starts neutral, a few mostly-happy initial owners. Does adoption
still spread, and does the network / arrangement now matter?

Uses nwom.run (vectorised committed dynamics plus the negative weight w).

    python lownoise.py probe
    python lownoise.py sweep
"""
from __future__ import annotations

import copy
import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT  # noqa: E402
import nwom  # noqa: E402
from nwom import base_settings, run  # noqa: E402

nwom.N_STEPS = 300

from heatpump_sim.settings import Settings  # noqa: E402

CHECKPOINTS = [50, 100, 150, 200, 300]


def configure(seed, mixing, noise, breakdown, lrf=0.3, initial_std=0.0):
    cfg = base_settings(mixing=mixing, seed=seed)
    cfg["opinions"]["noise_std"] = noise
    cfg["opinions"]["initial_std"] = initial_std
    cfg["heatpumps"]["breakdown_rate"] = breakdown
    cfg["network"]["params"]["long_range_fraction"] = lrf
    return cfg


def describe(h, hp, br, op):
    eligible = h.characteristic >= 0.30
    non_owner = ~hp[-1]
    return ({t: round(100 * hp[t].mean(), 1) for t in CHECKPOINTS},
            round(100 * br[-1].mean(), 1),
            # How close the remaining eligible non-owners are to their threshold.
            np.percentile(op[-1][eligible & non_owner], [10, 50, 90]).round(2) if (eligible & non_owner).any() else None,
            np.percentile((0.95 - 0.2 * h.characteristic)[eligible & non_owner], [10, 50, 90]).round(2)
            if (eligible & non_owner).any() else None)


def probe():
    for noise, breakdown, w in [(0.0, 0.0, 1), (0.0, 0.002, 1), (0.0, 0.002, 5), (0.02, 0.0, 1)]:
        t0 = time.time()
        h, _, hp, br, op = run(Settings(configure(1, 0.0, noise, breakdown)), float(w), net_key=("probe", 1))
        curve, broken, op_pct, thr_pct = describe(h, hp, br, op)
        print(f"noise {noise} breakdown {breakdown} w {w}: adoption {curve}  broken {broken}%  "
              f"eligible non-owners' opinion p10/50/90 {op_pct}, their threshold {thr_pct}  ({time.time() - t0:.0f}s)")


NOISES = [0.0, 0.02]
BREAKDOWNS = [0.0, 0.0002, 0.0005, 0.001, 0.002]
WEIGHTS = [1, 2, 5]
MIXINGS = [0.0, 1.0]
LONG_RANGE = [0.1, 0.5]
SEEDS = [1, 2, 3]


def sweep():
    rows = []
    t0 = time.time()
    for seed, mixing, lrf in itertools.product(SEEDS, MIXINGS, LONG_RANGE):
        for noise, breakdown in itertools.product(NOISES, BREAKDOWNS):
            for w in (WEIGHTS if breakdown > 0 else [1]):
                cfg = configure(seed, mixing, noise, breakdown, lrf)
                h, _, hp, br, op = run(Settings(cfg), float(w), net_key=(seed, mixing, lrf))
                eligible = h.characteristic >= 0.30
                frac = hp[:, eligible].mean(axis=1)
                row = {"seed": seed, "mixing": mixing, "long_range": lrf, "noise": noise,
                       "breakdown": breakdown, "w": w, "broken_t100": 100 * br[-1].mean(),
                       "t_half_eligible": int(np.argmax(frac >= 0.5)) if (frac >= 0.5).any() else np.nan}
                for t in CHECKPOINTS:
                    row[f"adopt_t{t}"] = 100 * hp[t].mean()
                rows.append(row)
        print(f"seed {seed} mixing {mixing:g} lrf {lrf} done ({time.time() - t0:.0f}s)", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "lownoise_runs.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 60)
    cols = [f"adopt_t{t}" for t in CHECKPOINTS] + ["broken_t100", "t_half_eligible"]
    print("\nMean over 3 seeds (% of households with a heat pump):")
    print(df.groupby(["noise", "breakdown", "w", "long_range", "mixing"])[cols].mean().round(1).to_string())
    print("\nSeed SD of adopt_t50:")
    print(df.groupby(["noise", "breakdown", "w", "long_range", "mixing"])["adopt_t50"].std().round(1)
          .unstack(["long_range", "mixing"]).to_string())


if __name__ == "__main__":
    {"probe": probe, "sweep": sweep}[sys.argv[1]]()
