"""(a) Recalibrate network options A and B to the base pace, rerun the
structure comparison; (c) negative word-of-mouth dose-response, measured on
totals and on gaps between LSOA types. Exploratory; the model code is untouched.

Pace target: mean adoption at 10 years over local/segregated and rewired
networks (top first owners, seeds 1-3), matched by tuning delta.

    python proto4.py calib | net <seeds> <tag> | dose <seeds> <tag> | report
"""
from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import proto3 as p3  # noqa: E402
from common import OUT  # noqa: E402

TO_CAL = {"A beta2": dict(beta=2.0), "B b0.5": dict(b=0.5), "B b0.9": dict(b=0.9),
          "A2+B0.9": dict(beta=2.0, b=0.9)}
CAL_PATH = OUT / "proto4_calibration.json"
TYPE_ORDER = ["t0", "t1", "t2", "t3", "t4", "t5"]


def pace(seeds=(1, 2, 3), **kw):
    vals = [p3.summary(s, lay, *p3.simulate(s, lay, **kw))
            for s in seeds for lay in ("local/segregated", "rewired")]
    return np.mean([v["adopt_m120"] for v in vals]), np.mean([v["adopt_m300"] for v in vals])


def calib():
    target, t300 = pace()
    print(f"base: 10 yr {target:.2f}%, 25 yr {t300:.2f}%", flush=True)
    out = {"base": {}}
    for name, kw in TO_CAL.items():
        lo, hi = np.log(0.06), np.log(1.0)
        for _ in range(9):
            mid = (lo + hi) / 2
            m120, m300 = pace(delta=float(np.exp(mid)), **kw)
            lo, hi = (mid, hi) if m120 < target else (lo, mid)
        d = float(np.exp((lo + hi) / 2))
        m120, m300 = pace(delta=d, **kw)
        out[name] = dict(kw, delta=d)
        print(f"{name}: delta {d:.3f} -> 10 yr {m120:.2f}%, 25 yr {m300:.2f}%", flush=True)
    CAL_PATH.write_text(json.dumps(out, indent=1))


def options():
    return json.loads(CAL_PATH.read_text())


def net(seeds, tag):
    rows, t0 = [], time.time()
    for seed in seeds:
        for layout, (opt, kw), initial in itertools.product(p3.LAYOUTS, options().items(), ["top", "random"]):
            rows.append({"seed": seed, "layout": layout, "option": opt, "initial": initial,
                         **p3.summary(seed, layout, *p3.simulate(seed, layout, initial=initial, **kw))})
        print(f"net {tag}: seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    pd.DataFrame(rows).to_csv(OUT / f"proto4_net_{tag}.csv", index=False)


DOSE = [(0.0, 1, np.inf)] + list(itertools.product([0.05, 0.1, 0.2], [1, 3], [12, np.inf]))
DOSE_LAYOUTS = ["local/segregated", "long-range/random", "rewired"]


def dose(seeds, tag):
    rows, t0 = [], time.time()
    for seed in seeds:
        for layout, (opt, kw), initial, (q, w, dur) in itertools.product(
                DOSE_LAYOUTS, options().items(), ["top", "random"], DOSE):
            rows.append({"seed": seed, "layout": layout, "option": opt, "initial": initial,
                         "q": q, "w": w, "duration": dur,
                         **p3.summary(seed, layout, *p3.simulate(seed, layout, initial=initial,
                                                                q_install=q, w=w, duration=dur, **kw))})
        print(f"dose {tag}: seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    pd.DataFrame(rows).to_csv(OUT / f"proto4_dose_{tag}.csv", index=False)


def report():
    pd.set_option("display.width", 250, "display.max_rows", 500, "display.max_columns", 40)
    order = list(options())
    print("Calibration:", json.dumps(options()))

    n = pd.concat([pd.read_csv(f) for f in sorted(OUT.glob("proto4_net_*.csv"))])
    n["option"] = pd.Categorical(n.option, order)
    print(f"\n(a) recalibrated structure comparison, {n.seed.nunique()} seeds")
    for metric in ["adopt_m120", "adopt_m300", "type_range_m120", "type_range_m300", "cluster_at5"]:
        print(f"\n{metric}")
        print(n.groupby(["option", "initial", "layout"], observed=True)[metric].mean().round(2)
              .unstack(["initial", "layout"]).to_string())
    for t in (120, 300):
        g = n.groupby(["option", "initial", "layout"], observed=True)[f"adopt_m{t}"].mean().unstack("layout")
        eff = pd.DataFrame({"local-long(seg)": g["local/segregated"] - g["long-range/segregated"],
                            "seg-random(local)": g["local/segregated"] - g["local/random"],
                            "real-rewired": g["local/segregated"] - g["rewired"]})
        print(f"\nStructure effects on adoption at month {t} (points)")
        print(eff.round(2).unstack("initial").to_string())
    print("\nmax seed SD of adopt_m120:", n.groupby(["option", "initial", "layout"], observed=True)
          ["adopt_m120"].std().max().round(2))

    d = pd.concat([pd.read_csv(f) for f in sorted(OUT.glob("proto4_dose_*.csv"))])
    d["option"] = pd.Categorical(d.option, order)
    keys = ["option", "layout", "initial", "seed"]
    base = d[d.q == 0].set_index(keys)
    x = d[d.q > 0].copy()
    idx = pd.MultiIndex.from_frame(x[keys])
    tcols = [c for c in d.columns if c[:5] in ("m120_", "m300_")]
    for t in (120, 300):
        x[f"short_m{t}"] = 100 * (1 - x[f"adopt_m{t}"].to_numpy() / base.loc[idx, f"adopt_m{t}"].to_numpy())
        x[f"gap_change_m{t}"] = x[f"type_range_m{t}"].to_numpy() - base.loc[idx, f"type_range_m{t}"].to_numpy()
    for c in tcols:
        x[f"short_{c}"] = 100 * (1 - x[c].to_numpy() / base.loc[idx, c].to_numpy())
    print(f"\n(c) dose-response, {d.seed.nunique()} seeds")
    for metric in ["short_m120", "short_m300", "gap_change_m120", "gap_change_m300"]:
        print(f"\n{metric}: mean over seeds and first-owner placements (columns q)")
        print(x.groupby(["option", "layout", "duration", "w", "q"], observed=True)[metric].mean().round(1)
              .unstack("q").to_string())
    print("\nShortfall by LSOA type (%), q 0.1, w 1, permanent complaints, local/segregated, top first owners")
    sel = x[(x.q == 0.1) & (x.w == 1) & np.isinf(x.duration) & (x.layout == "local/segregated") & (x.initial == "top")]
    print(sel.groupby("option", observed=True)[[f"short_m120_{t}" for t in TYPE_ORDER if f"short_m120_{t}" in sel]
                                                + [f"short_m300_{t}" for t in TYPE_ORDER if f"short_m300_{t}" in sel]]
          .mean().round(1).to_string())
    print("\nBaseline adoption by type (no dissatisfaction, local/segregated, top):")
    b = d[(d.q == 0) & (d.layout == "local/segregated") & (d.initial == "top")]
    print(b.groupby("option", observed=True)[[c for c in tcols if c in b]].mean().round(1).to_string())


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "calib":
        calib()
    elif cmd in ("net", "dose"):
        {"net": net, "dose": dose}[cmd]([int(s) for s in sys.argv[2].split(",")], sys.argv[3])
    else:
        report()
