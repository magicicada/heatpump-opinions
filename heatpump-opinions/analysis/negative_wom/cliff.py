"""Three follow-ups on the low-noise variant (noise 0, everyone starts at 0.5):

A. Chance of takeoff near the cliff: 20 seeds over a fine grid of
   bad-experience rates (w = 1), per network x arrangement.
B. The same with initial owners drawn at random rather than from the top
   10% by characteristic, to separate "segregation" from "early adopters
   start next to each other".
C. Decay: a broken owner's voice fades with a half-life, at doses past the
   cliff (initial owners as committed, 10 seeds).

Takeoff = more than half of all households have a heat pump at step 300.

    python cliff.py time | A | B | C | report
"""
from __future__ import annotations

import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import nwom  # noqa: E402
from common import OUT  # noqa: E402
from lownoise import configure  # noqa: E402

from heatpump_sim.settings import Settings  # noqa: E402

nwom.N_STEPS = 300
SCENARIOS = list(itertools.product([0.1, 0.5], [0.0, 1.0]))  # (long_range, mixing)
RATES = [0.0, 0.0005, 0.001, 0.0015, 0.002, 0.003]
HALF_LIVES = [None, 50, 20, 10]
DECAY_RATES = [0.001, 0.002, 0.003, 0.005]


def one(seed, lrf, mixing, rate, initial="top", half_life=None):
    cfg = configure(seed, mixing, 0.0, rate, lrf)
    if initial == "random":
        cfg["heatpumps"]["top_pool_fraction"] = 1.0
    h, _, hp, br, _ = nwom.run(Settings(cfg), 1.0, net_key=(seed, mixing, lrf), half_life=half_life)
    eligible = h.characteristic >= 0.30
    frac = hp[:, eligible].mean(axis=1)
    return {"seed": seed, "long_range": lrf, "mixing": mixing, "rate": rate, "initial": initial,
            "half_life": half_life if half_life is not None else np.inf,
            "adopt_t100": 100 * hp[100].mean(), "adopt_t200": 100 * hp[200].mean(),
            "adopt_t300": 100 * hp[300].mean(), "broken_t300": 100 * br[300].mean(),
            "t_half_eligible": int(np.argmax(frac >= 0.5)) if (frac >= 0.5).any() else np.nan}


def sweep(name, jobs):
    rows, t0 = [], time.time()
    for k, job in enumerate(jobs, 1):
        rows.append(one(**job))
        if k % 40 == 0:
            print(f"{name}: {k}/{len(jobs)} ({time.time() - t0:.0f}s)", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"cliff_{name}.csv", index=False)
    print(f"{name} done: {len(jobs)} runs in {time.time() - t0:.0f}s", flush=True)


def jobs_ab(initial):
    return [dict(seed=s, lrf=l, mixing=m, rate=r, initial=initial)
            for s in range(1, 21) for l, m in SCENARIOS for r in RATES]


def jobs_c():
    return [dict(seed=s, lrf=l, mixing=m, rate=r, half_life=hl)
            for s in range(1, 11) for l, m in SCENARIOS for r in DECAY_RATES for hl in HALF_LIVES]


def summarise(df, keys):
    g = df.groupby(keys)
    return pd.DataFrame({
        "p_takeoff": 100 * g["adopt_t300"].apply(lambda s: (s > 50).mean()),
        "adopt_t300": g["adopt_t300"].mean(),
        "t_half_if_takeoff": df[df.adopt_t300 > 50].groupby(keys)["t_half_eligible"].median(),
        "broken_t300": g["broken_t300"].mean(),
        "n": g.size(),
    }).round(1)


def report():
    pd.set_option("display.width", 220, "display.max_rows", 500)
    ab = pd.concat([pd.read_csv(OUT / f"cliff_{x}.csv") for x in ("A", "B") if (OUT / f"cliff_{x}.csv").exists()])
    ab["scenario"] = np.where(ab.long_range == 0.1, "local", "long-range") + "/" + \
        np.where(ab.mixing == 0, "segregated", "random")
    s = summarise(ab, ["initial", "scenario", "rate"])
    print("A/B: % of 20 seeds that take off, by rate of bad experiences (w = 1, noise 0)")
    print(s["p_takeoff"].unstack("rate").to_string())
    print("\nMedian step at which half of eligible have adopted (runs that take off)")
    print(s["t_half_if_takeoff"].unstack("rate").to_string())
    c_path = OUT / "cliff_C.csv"
    if c_path.exists():
        c = pd.read_csv(c_path)
        c["scenario"] = np.where(c.long_range == 0.1, "local", "long-range") + "/" + \
            np.where(c.mixing == 0, "segregated", "random")
        sc = summarise(c, ["scenario", "half_life", "rate"])
        print("\nC: % of 10 seeds that take off, by voice half-life (rows) and rate (columns)")
        print(sc["p_takeoff"].unstack("rate").to_string())
        print("\nC: median step to half of eligible (runs that take off)")
        print(sc["t_half_if_takeoff"].unstack("rate").to_string())


def time_it():
    t0 = time.time(); one(1, 0.1, 0.0, 0.001); t1 = time.time(); one(1, 0.1, 0.0, 0.001, half_life=20)
    print(f"first (with network build) {t1 - t0:.1f}s, cached {time.time() - t1:.1f}s")


if __name__ == "__main__":
    arg = sys.argv[1]
    if arg == "time":
        time_it()
    elif arg == "A":
        sweep("A", jobs_ab("top"))
    elif arg == "B":
        sweep("B", jobs_ab("random"))
    elif arg == "C":
        sweep("C", jobs_c())
    else:
        report()
