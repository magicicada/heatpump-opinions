"""Prototype of the proposed mechanism (exploratory; the model code is untouched).

One step = one month. Reuses the committed world files and spatial_kernel
network; replaces the dynamics:

1. Experience-based word of mouth. Only owners talk. Each month an owner
   talks to each contact with probability contact_local / contact_long
   (by edge kind; DESIGN.md: 0.72 and 0.25 a month). A positive message moves
   the listener's motivation m a fraction delta of the way to 1:
       m <- 1 - (1 - m) * (1 - delta)
   A negative message counts as w positive-equivalents downwards:
       m <- m * (1 - delta) ** w
   Motivation relaxes back to the household's own baseline m0 at rate
   `memory` each month, so what people hear fades.
2. Trigger -> choice. Each month a non-owner has a trigger (boiler
   replacement, moving, renovation) with probability `trigger`. Memoryless,
   so a household that passes on a heat pump waits on average 1/trigger
   months for the next chance -- that is the lock-in. When triggered, a
   household past the capability gate adopts with probability
       logistic((m - m50_i) / slope),  m50_i = m50 - char_weight * characteristic
3. Dissatisfaction. A new owner is dissatisfied with probability q_install;
   satisfied owners can later become dissatisfied at rate q_later a month.
   Dissatisfied owners talk negatively for a mean of `duration` months (then
   fall silent); satisfied owners keep talking positively.

    python proto.py probe | checks | report
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
import nwom  # noqa: E402
from common import OUT  # noqa: E402

from heatpump_sim.agents import initialize_households  # noqa: E402
from heatpump_sim.network import build_network  # noqa: E402
from heatpump_sim.settings import Settings  # noqa: E402

DEFAULTS = dict(
    months=300,
    initial_fraction=0.01,     # ~1% of homes have a heat pump today
    initial="top",             # "top": drawn from the top 10% by characteristic; "random": from everyone
    contact_local=0.72, contact_long=0.25,
    delta=0.03, memory=0.05, m0_mean=0.5, m0_sd=0.15,
    trigger=1 / 180,           # ~15-year boiler life
    m50=0.8, char_weight=0.2, slope=0.07, gate=0.30,
    q_install=0.0, q_later=0.0, w=1.0, duration=np.inf,
)
CHECK_MONTHS = [60, 120, 180, 240, 300]

_NETS: dict = {}


def network(seed, mixing, lrf):
    key = (seed, mixing, lrf)
    if key not in _NETS:
        cfg = nwom.base_settings(mixing=mixing, seed=seed)
        cfg["network"]["params"]["long_range_fraction"] = lrf
        s = Settings(cfg)
        rng = np.random.default_rng(seed)
        h = initialize_households(s, rng)
        g = build_network(h.locations, s, rng)
        e = np.array([(u, v, k == "local") for u, v, k in g.edges(data="kind")], dtype=np.int64).reshape(-1, 3)
        src = np.concatenate([e[:, 0], e[:, 1]])
        dst = np.concatenate([e[:, 1], e[:, 0]])
        local = np.concatenate([e[:, 2], e[:, 2]]).astype(bool)
        _NETS[key] = (h.characteristic.copy(), src, dst, local)
    return _NETS[key]


def simulate(seed=1, mixing=0.0, lrf=0.3, **kw):
    p = {**DEFAULTS, **kw}
    char, src, dst, local = network(seed, mixing, lrf)
    n = len(char)
    rng = np.random.default_rng(1000 + seed)
    rate = np.where(local, p["contact_local"], p["contact_long"])

    m0 = np.clip(rng.normal(p["m0_mean"], p["m0_sd"], n), 0, 1)
    m = m0.copy()
    n_init = round(p["initial_fraction"] * n)
    pool = np.argsort(char)[-round(0.10 * n):] if p["initial"] == "top" else np.arange(n)
    owner = np.zeros(n, bool)
    owner[rng.choice(pool, n_init, replace=False)] = True
    diss = owner & (rng.random(n) < p["q_install"])
    talking_neg = diss.copy()
    eligible = char >= p["gate"]
    m50 = p["m50"] - p["char_weight"] * char
    stop = 0.0 if np.isinf(p["duration"]) else 1.0 / p["duration"]

    adopt_hist = np.zeros(p["months"] + 1)
    diss_hist = np.zeros(p["months"] + 1)
    elig_hist = np.zeros(p["months"] + 1)
    adopt_hist[0], diss_hist[0], elig_hist[0] = owner.mean(), diss.mean(), owner[eligible].mean()
    for t in range(1, p["months"] + 1):
        pos_spk = owner & ~diss
        spk = pos_spk | talking_neg
        live = np.nonzero(spk[src])[0]
        live = live[rng.random(len(live)) < rate[live]]
        is_pos = pos_spk[src[live]]
        n_pos = np.bincount(dst[live[is_pos]], minlength=n)
        n_neg = np.bincount(dst[live[~is_pos]], minlength=n)

        m = m + p["memory"] * (m0 - m)
        m = 1 - (1 - m) * (1 - p["delta"]) ** n_pos
        m = m * (1 - p["delta"]) ** (p["w"] * n_neg)

        talking_neg &= ~(rng.random(n) < stop)
        later = owner & ~diss & (rng.random(n) < p["q_later"])
        diss |= later
        talking_neg |= later

        trig = ~owner & eligible & (rng.random(n) < p["trigger"])
        prob = 1 / (1 + np.exp(-(m - m50) / p["slope"]))
        new = trig & (rng.random(n) < prob)
        owner |= new
        new_diss = new & (rng.random(n) < p["q_install"])
        diss |= new_diss
        talking_neg |= new_diss

        adopt_hist[t], diss_hist[t], elig_hist[t] = owner.mean(), diss.mean(), owner[eligible].mean()
    return adopt_hist, diss_hist, elig_hist, m


def summary(hist, elig):
    row = {f"adopt_m{t}": 100 * hist[t] for t in CHECK_MONTHS}
    row["t_half_elig_yrs"] = (np.argmax(elig >= 0.5) / 12) if (elig >= 0.5).any() else np.nan
    yearly = np.diff(hist[::12]) * 100
    row["peak_yr_install_pct"] = yearly.max()
    row["peak_year"] = int(yearly.argmax()) + 1
    row["yr1_install_pct"] = yearly[0]
    return row


def probe():
    for kw in [dict(), dict(q_install=0.1), dict(q_install=0.1, w=3), dict(q_install=0.3, w=3),
               dict(initial="random")]:
        t0 = time.time()
        a, d, e, m = simulate(**kw)
        s = summary(a, e)
        print(kw or "baseline", {k: round(v, 1) for k, v in s.items()},
              f"diss {100 * d[-1]:.1f}%  mean m {m.mean():.2f}  ({time.time() - t0:.1f}s)")


SCEN = {"local/segregated": (0.0, 0.1), "local/random": (1.0, 0.1),
        "long-range/segregated": (0.0, 0.5), "long-range/random": (1.0, 0.5)}
SEEDS = range(1, 11)


def checks():
    rows, t0 = [], time.time()

    def rec(check, scen, seed, **kw):
        mixing, lrf = SCEN[scen]
        a, d, e, _ = simulate(seed=seed, mixing=mixing, lrf=lrf, **kw)
        rows.append({"check": check, "scenario": scen, "seed": seed, **kw, **summary(a, e),
                     "diss_m300": 100 * d[-1]})

    for seed in SEEDS:
        for scen in SCEN:
            for initial in ("top", "random"):          # checks 1-3
                rec("baseline", scen, seed, initial=initial)
        rec("no_wom", "local/segregated", seed, delta=0.0)          # does word of mouth drive it?
        for q, w in itertools.product([0.0, 0.5, 1.0], [1, 5]):   # check 4: extremes
            rec("extremes", "local/segregated", seed, q_install=q, w=w)
        for scen in ("local/segregated", "long-range/random"):   # dose-response
            for q, w, dur in itertools.product([0.05, 0.1, 0.2, 0.4], [1, 3], [6, 24, np.inf]):
                rec("dose", scen, seed, q_install=q, w=w, duration=dur)
        print(f"seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    pd.DataFrame(rows).to_csv(OUT / "proto_checks.csv", index=False)
    report()


def report():
    df = pd.read_csv(OUT / "proto_checks.csv")
    pd.set_option("display.width", 230, "display.max_rows", 300, "display.max_columns", 40)
    cols = [f"adopt_m{t}" for t in CHECK_MONTHS] + ["t_half_elig_yrs", "yr1_install_pct", "peak_yr_install_pct", "peak_year"]
    b = df[df.check == "baseline"]
    print("Checks 1-3: no dissatisfaction. Mean (seed SD) over 10 seeds")
    mean = b.groupby(["initial", "scenario"])[cols].mean().round(1)
    print(mean.to_string())
    print("seed SD:")
    print(b.groupby(["initial", "scenario"])[["adopt_m120", "adopt_m300", "t_half_elig_yrs"]].std().round(2).to_string())
    print("\nNo word of mouth (delta = 0), local/segregated:")
    print(df[df.check == "no_wom"][cols].mean().round(1).to_string())
    x = df[df.check == "extremes"]
    print("\nCheck 4: extremes (local/segregated)")
    print(x.groupby(["q_install", "w"])[cols + ["diss_m300"]].mean().round(1).to_string())
    d = df[df.check == "dose"].copy()
    base = b[b.initial == "top"].set_index(["scenario", "seed"])
    for t in (120, 240):
        ref = base.loc[pd.MultiIndex.from_frame(d[["scenario", "seed"]]), f"adopt_m{t}"].to_numpy()
        d[f"short_m{t}"] = 100 * (1 - d[f"adopt_m{t}"] / ref)
    d["dose"] = d.q_install * d.w * np.where(np.isinf(d.duration), 300, d.duration)
    print("\nDose-response: % shortfall vs no dissatisfaction at 10 and 20 years; years to half of eligible")
    g = d.groupby(["scenario", "duration", "w", "q_install"])[["short_m120", "short_m240", "t_half_elig_yrs", "diss_m300"]].mean()
    print(g.round(1).unstack("q_install").to_string())


if __name__ == "__main__":
    {"probe": probe, "checks": checks, "report": report}[sys.argv[1]]()
