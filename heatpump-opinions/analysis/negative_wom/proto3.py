"""Network options for the prototype (exploratory; the model code is untouched).

Same mechanism as proto.py at the calibrated setting (m0_mean 0.3, delta 0.06),
with equal contact rates on all ties, plus three switchable options:

A. Complex contagion (beta). Hearing from several *different* owners in a
   month counts for more than one owner: the month's positive push is
       n_eff = n_msgs * (d / D_REF) ** (beta - 1)
   where d is the number of distinct owners heard. beta = 1 is off; with
   D_REF = 2, a lone voice counts less and three or more count more.
B. Credibility from similar homes (b). A message from an owner with a
   different building type counts (1 - b); same type counts 1. b = 0 is off.
C. Sparse discussion network (p_keep). Only a share p_keep of ties carry heat
   pump talk; their contact rate is scaled up (Poisson messages) so each
   owner sends the same expected number of messages. p_keep = 1 is off.

Null: "rewired" keeps everyone's number of contacts but shuffles who they are
(configuration model on the local/segregated network). If an option's results
are the same on the rewired network, structure doesn't matter under it.

    python proto3.py run <seeds e.g. 1,2,3> <tag> | report
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

P = dict(months=300, initial_fraction=0.01, initial="top", contact=0.72, delta=0.06, memory=0.05,
         m0_mean=0.3, m0_sd=0.15, trigger=1 / 180, m50=0.8, char_weight=0.2, slope=0.07, gate=0.30,
         beta=1.0, b=0.0, p_keep=1.0, q_install=0.0, w=1.0, duration=np.inf)
D_REF = 2.0
MONTHS = [60, 120, 180, 300]
LAYOUTS = {"local/segregated": (0.0, 0.1), "local/random": (1.0, 0.1),
           "long-range/segregated": (0.0, 0.5), "long-range/random": (1.0, 0.5),
           "rewired": (0.0, 0.1)}
OPTIONS = {"base": {}, "A beta1.5": dict(beta=1.5), "A beta2": dict(beta=2.0),
           "B b0.5": dict(b=0.5), "B b0.9": dict(b=0.9),
           "C deg5": dict(p_keep=1 / 3), "C deg3": dict(p_keep=0.2),
           "A2+B0.9": dict(beta=2.0, b=0.9), "A2+C3": dict(beta=2.0, p_keep=0.2)}

_W: dict = {}


def world(seed, layout):
    mixing, lrf = LAYOUTS[layout]
    key = (seed, layout)
    if key not in _W:
        cfg = nwom.base_settings(mixing=mixing, seed=seed)
        cfg["network"]["params"]["long_range_fraction"] = lrf
        s = Settings(cfg)
        rng = np.random.default_rng(seed)
        h = initialize_households(s, rng)
        g = build_network(h.locations, s, rng)
        n = h.n
        e = np.array(list(g.edges()), dtype=np.int64).reshape(-1, 2)
        spatial = e                                    # the network clustering is measured on
        if layout == "rewired":
            r = np.random.default_rng(5000 + seed)
            stubs = np.repeat(np.arange(n), np.bincount(e.ravel(), minlength=n))
            r.shuffle(stubs)
            pairs = np.sort(stubs[: len(stubs) // 2 * 2].reshape(-1, 2), axis=1)
            e = np.unique(pairs[pairs[:, 0] != pairs[:, 1]], axis=0)
        attr = h.attributes
        _W[key] = dict(char=h.characteristic.copy(), e=e, spatial=spatial,
                       btype=pd.factorize(attr["building_type"])[0],
                       arch=np.asarray(attr["lsoa_archetype"]))
    return _W[key]


def simulate(seed, layout, **kw):
    p = {**P, **kw}
    W = world(seed, layout)
    char, n = W["char"], len(W["char"])
    rng = np.random.default_rng(1000 + seed)
    e = W["e"]
    if p["p_keep"] < 1:
        e = e[np.random.default_rng(7000 + seed).random(len(e)) < p["p_keep"]]
    src = np.concatenate([e[:, 0], e[:, 1]])
    dst = np.concatenate([e[:, 1], e[:, 0]])
    sim = np.where(W["btype"][src] == W["btype"][dst], 1.0, 1.0 - p["b"])
    rate = p["contact"] / p["p_keep"]
    poisson = p["p_keep"] < 1

    m0 = np.clip(rng.normal(p["m0_mean"], p["m0_sd"], n), 0, 1)
    m = m0.copy()
    pool = np.argsort(char)[-round(0.10 * n):] if p["initial"] == "top" else np.arange(n)
    owner = np.zeros(n, bool)
    owner[rng.choice(pool, round(p["initial_fraction"] * n), replace=False)] = True
    diss = owner & (rng.random(n) < p["q_install"])
    talking_neg = diss.copy()
    eligible = char >= p["gate"]
    m50 = p["m50"] - p["char_weight"] * char
    stop = 0.0 if np.isinf(p["duration"]) else 1.0 / p["duration"]

    def push(edges, k):
        n_msg = np.bincount(dst[edges], weights=k * sim[edges], minlength=n)
        if p["beta"] == 1:
            return n_msg
        d = np.bincount(dst[edges], weights=sim[edges], minlength=n)
        return n_msg * (d / D_REF) ** (p["beta"] - 1)

    hist, elig_hist = np.zeros(p["months"] + 1), np.zeros(p["months"] + 1)
    hist[0], elig_hist[0] = owner.mean(), owner[eligible].mean()
    snaps = {}
    for t in range(1, p["months"] + 1):
        pos_spk = owner & ~diss
        live = np.nonzero((pos_spk | talking_neg)[src])[0]
        if poisson:
            k = rng.poisson(rate, len(live)).astype(float)
            live, k = live[k > 0], k[k > 0]
        else:
            live = live[rng.random(len(live)) < rate]
            k = np.ones(len(live))
        is_pos = pos_spk[src[live]]
        m = m + p["memory"] * (m0 - m)
        m = 1 - (1 - m) * (1 - p["delta"]) ** push(live[is_pos], k[is_pos])
        m = m * (1 - p["delta"]) ** (p["w"] * push(live[~is_pos], k[~is_pos]))

        talking_neg &= ~(rng.random(n) < stop)
        trig = ~owner & eligible & (rng.random(n) < p["trigger"])
        new = trig & (rng.random(n) < 1 / (1 + np.exp(-(m - m50) / p["slope"])))
        owner |= new
        nd = new & (rng.random(n) < p["q_install"])
        diss |= nd
        talking_neg |= nd
        hist[t], elig_hist[t] = owner.mean(), owner[eligible].mean()
        if "c5" not in snaps and hist[t] >= 0.05:
            snaps["c5"] = clustering(owner, W["spatial"], n)
        if t == 120:
            snaps["c120"] = clustering(owner, W["spatial"], n)
            snaps["owner120"] = owner.copy()
    snaps["owner300"] = owner.copy()
    return hist, elig_hist, snaps, eligible


def clustering(owner, e, n):
    """Share of an owner's spatial-network neighbours who are owners, over the
    share expected if owners were scattered at random (1 = no clustering)."""
    u, v = e[:, 0], e[:, 1]
    deg = np.bincount(e.ravel(), minlength=n)
    own_nb = np.bincount(u, weights=owner[v], minlength=n) + np.bincount(v, weights=owner[u], minlength=n)
    frac = own_nb[owner] / np.maximum(deg[owner], 1)
    return frac.mean() / owner.mean()


def summary(seed, layout, hist, elig, snaps, eligible):
    row = {f"adopt_m{t}": 100 * hist[t] for t in MONTHS}
    row["t_half_elig_yrs"] = np.argmax(elig >= 0.5) / 12 if (elig >= 0.5).any() else np.nan
    yearly = np.diff(hist[::12]) * 100
    row.update(yr1_install_pct=yearly[0], peak_yr_install_pct=yearly.max(), peak_year=int(yearly.argmax()) + 1,
               cluster_at5=snaps.get("c5", np.nan), cluster_m120=snaps.get("c120", np.nan))
    arch = world(seed, layout)["arch"]
    for t in (120, 300):
        o = snaps[f"owner{t}"]
        by = {a: 100 * o[(arch == a) & eligible].mean() for a in np.unique(arch) if ((arch == a) & eligible).sum() > 50}
        row[f"type_range_m{t}"] = max(by.values()) - min(by.values())
        row.update({f"m{t}_{a[:2]}": v for a, v in by.items()})
    return row


def run(seeds, tag):
    rows, t0 = [], time.time()
    for seed in seeds:
        for layout, (opt, kw), initial in itertools.product(LAYOUTS, OPTIONS.items(), ["top", "random"]):
            out = simulate(seed, layout, initial=initial, **kw)
            rows.append({"seed": seed, "layout": layout, "option": opt, "initial": initial,
                         **summary(seed, layout, *out)})
        print(f"{tag}: seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    pd.DataFrame(rows).to_csv(OUT / f"proto3_{tag}.csv", index=False)


def report():
    df = pd.concat([pd.read_csv(f) for f in sorted(OUT.glob("proto3_*.csv"))])
    pd.set_option("display.width", 250, "display.max_rows", 400, "display.max_columns", 40)
    order = list(OPTIONS)
    df["option"] = pd.Categorical(df.option, order)
    print(f"{df.seed.nunique()} seeds")
    for metric in ["adopt_m120", "adopt_m300", "yr1_install_pct", "cluster_at5", "type_range_m120"]:
        print(f"\n{metric}: mean over seeds (rows option, columns layout x first owners)")
        print(df.groupby(["option", "initial", "layout"], observed=True)[metric].mean().round(2)
              .unstack(["initial", "layout"]).to_string())
    sd = df.groupby(["option", "initial", "layout"], observed=True)["adopt_m120"].std()
    print("\nmax seed SD of adopt_m120 per option:")
    print(sd.groupby("option", observed=True).max().round(2).to_string())
    # Structure effect per option: spread of 10-year adoption across layouts, and gap to the rewired null.
    g = df.groupby(["option", "initial", "layout"], observed=True)["adopt_m120"].mean().unstack("layout")
    eff = pd.DataFrame({
        "local - long (seg)": g["local/segregated"] - g["long-range/segregated"],
        "seg - random (local)": g["local/segregated"] - g["local/random"],
        "real - rewired": g["local/segregated"] - g["rewired"],
    })
    top = df[df.initial == "top"].groupby(["option", "layout"], observed=True)["adopt_m120"].mean()
    rnd = df[df.initial == "random"].groupby(["option", "layout"], observed=True)["adopt_m120"].mean()
    print("\nStructure effects on adoption at 10 years (percentage points):")
    print(eff.round(2).unstack("initial").to_string())
    print("\nTop - random first owners, adoption at 10 years (points):")
    print((top - rnd).round(2).unstack("layout").to_string())


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run([int(s) for s in sys.argv[2].split(",")], sys.argv[3])
    else:
        report()
