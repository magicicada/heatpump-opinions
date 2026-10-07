"""Follow-ups on proto.py before the 7 Oct meeting (exploratory).

calib : find a baseline motivation (m0_mean) and WOM strength (delta) that give
        year-1 installs near the current UK rate (~0.35% of homes a year;
        ~100k installs / ~28m homes -- rough, unverified).
fixes : at the calibrated setting, rerun the network check with equal contact
        rates for local and long ties, top vs random first owners, and the
        dose-response for dissatisfaction.

    python proto2.py calib | fixes A|B | report
"""
from __future__ import annotations

import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT  # noqa: E402
from proto import SCEN, simulate, summary  # noqa: E402


def calib():
    t0 = time.time()
    for m0, delta in itertools.product([0.5, 0.4, 0.3, 0.25, 0.2], [0.03, 0.06, 0.1]):
        rows = []
        for seed in (1, 2):
            a, _, e, _ = simulate(seed=seed, m0_mean=m0, delta=delta)
            rows.append(summary(a, e))
        s = pd.DataFrame(rows).mean()
        print(f"m0 {m0:.2f} delta {delta:.2f}: yr1 {s.yr1_install_pct:.2f}%  peak {s.peak_yr_install_pct:.1f}%"
              f" in yr {s.peak_year:.0f}  adopt 10/25 yr {s.adopt_m120:.1f}/{s.adopt_m300:.1f}"
              f"  ({time.time() - t0:.0f}s)", flush=True)


CAL = dict(m0_mean=float(sys.argv[2]) if len(sys.argv) > 3 and sys.argv[1] == "fixes" else 0.3,
           delta=float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[1] == "fixes" else 0.06)
SEEDS = range(1, 11)


def fixes(part):
    rows, t0 = [], time.time()
    for seed in SEEDS:
        for scen, (mixing, lrf) in SCEN.items():
            if part == "A":   # network check: contact rates, first-owner placement
                for equal, initial in itertools.product([False, True], ["top", "random"]):
                    kw = dict(CAL, initial=initial, contact_long=0.72 if equal else 0.25)
                    a, d, e, _ = simulate(seed=seed, mixing=mixing, lrf=lrf, **kw)
                    rows.append({"part": "net", "scenario": scen, "seed": seed, "equal_contact": equal,
                                 **kw, **summary(a, e)})
            else:             # dose-response at the calibrated setting, equal contact rates
                for q, w, dur in [(0, 1, np.inf)] + list(itertools.product([0.05, 0.1, 0.2], [0, 1, 3], [12, np.inf])):
                    kw = dict(CAL, contact_long=0.72, q_install=q, w=w, duration=dur)
                    a, d, e, _ = simulate(seed=seed, mixing=mixing, lrf=lrf, **kw)
                    rows.append({"part": "dose", "scenario": scen, "seed": seed, **kw, **summary(a, e),
                                 "diss_m300": 100 * d[-1]})
        print(f"{part}: seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    pd.DataFrame(rows).to_csv(OUT / f"proto2_{part}.csv", index=False)


def report():
    pd.set_option("display.width", 230, "display.max_rows", 300, "display.max_columns", 40)
    cols = ["adopt_m60", "adopt_m120", "adopt_m180", "adopt_m300", "t_half_elig_yrs",
            "yr1_install_pct", "peak_yr_install_pct", "peak_year"]
    a = pd.read_csv(OUT / "proto2_A.csv")
    print("Network check (calibrated, no dissatisfaction): mean over seeds")
    print(a.groupby(["equal_contact", "initial", "scenario"])[cols].mean().round(1).to_string())
    print("seed SD of adoption at 10 and 25 years:")
    print(a.groupby(["equal_contact", "initial", "scenario"])[["adopt_m120", "adopt_m300"]].std().round(2).to_string())
    b = pd.read_csv(OUT / "proto2_B.csv")
    base = b[b.q_install == 0].set_index(["scenario", "seed"])
    d = b[b.q_install > 0].copy()
    for t in (120, 300):
        ref = base.loc[pd.MultiIndex.from_frame(d[["scenario", "seed"]]), f"adopt_m{t}"].to_numpy()
        d[f"short_m{t}"] = 100 * (1 - d[f"adopt_m{t}"] / ref)
    print("\nBaseline for dose-response (equal contact rates):")
    print(base.groupby("scenario")[cols].mean().round(1).to_string())
    print("\nDose-response: % shortfall at 10 years (mean over seeds)")
    print(d.groupby(["scenario", "duration", "w", "q_install"])["short_m120"].mean().round(1)
          .unstack("q_install").to_string())
    print("\nDose-response: % shortfall at 25 years")
    print(d.groupby(["scenario", "duration", "w", "q_install"])["short_m300"].mean().round(1)
          .unstack("q_install").to_string())
    print("\nseed SD of 10-year shortfall (max over cells):", d.groupby(["scenario", "duration", "w", "q_install"])
          ["short_m120"].std().max().round(2))


if __name__ == "__main__":
    {"calib": calib, "fixes": lambda: fixes(sys.argv[-1]), "report": report}[sys.argv[1]]()
