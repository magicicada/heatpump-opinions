"""Negative word of mouth as a weight: how strong must a bad experience be to matter?

Exploratory variant of the model. A broken (dissatisfied) owner counts as
`w` voices in each contact's neighbour mean instead of 1:

    neighbour_mean_i = sum_j wt_j * o_j / sum_j wt_j,  wt_j = w if j broken else 1

w = 1 is the committed model. Everything else is heatpump_sim as pulled
(spatial_kernel network, dynamics otherwise unchanged); the repo is not edited.

Usage:
    python nwom.py check     # vectorised w=1 step vs the committed step
    python nwom.py time      # time one run
    python nwom.py sweep     # the sweep
"""
from __future__ import annotations

import copy
import functools
import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT, PROJECT, build_archetypes  # noqa: E402

from heatpump_sim import dynamics  # noqa: E402
from heatpump_sim.agents import initialize_households  # noqa: E402
from heatpump_sim.network import build_network  # noqa: E402
from heatpump_sim.settings import Settings  # noqa: E402
from heatpump_sim.worldgen import generate_and_write  # noqa: E402

N_STEPS = 100
CHECKPOINTS = [10, 25, 50, 75, 100]


def edge_arrays(graph, n):
    e = np.array(list(graph.edges()), dtype=np.int64).reshape(-1, 2)
    src = np.concatenate([e[:, 0], e[:, 1]])
    dst = np.concatenate([e[:, 1], e[:, 0]])
    return src, dst, np.bincount(src, minlength=n)


def opinion_update_weighted(h, edges, settings, rng, w):
    """dynamics.opinion_update_step, vectorised, with broken contacts weighted
    by w (a scalar, or a per-household array for decaying voices). Random
    draws are made in the same order as the committed loop."""
    src, dst, deg = edges
    social = settings.get("opinions.social_influence_rate", 0.15)
    self_inc = settings.get("opinions.self_increase_rate", 0.03)
    noise_std = settings.get("opinions.noise_std", 0.02)
    breakdown_rate = settings.get("heatpumps.breakdown_rate", 0.01)
    n = len(h.opinion)

    o = h.opinion
    wt = np.where(h.broken_down, w, 1.0)
    num = np.bincount(src, weights=(wt * o)[dst], minlength=n)
    den = np.bincount(src, weights=wt[dst], minlength=n)
    nmean = np.where(deg > 0, num / np.where(den > 0, den, 1.0), o)

    active = ~h.broken_down
    delta = social * (nmean - o) + np.where(h.has_heatpump, self_inc, 0.0)
    noise = np.zeros(n)
    noise[active] = rng.normal(0, noise_std, size=int(active.sum()))
    new = o.copy()
    new[active] = np.clip(o[active] + delta[active] + noise[active], 0.0, 1.0)
    h.opinion = new

    at_risk = np.where(h.has_heatpump & ~h.broken_down)[0]
    newly = at_risk[rng.random(len(at_risk)) < breakdown_rate]
    h.broken_down[newly] = True
    h.opinion[newly] = 0.0


_NET_CACHE: dict = {}


def run(settings, w, net_key=None, committed=False, half_life=None):
    """Mirror of simulate.run_simulation. The network (and the rng state just
    after building it) is cached per net_key, so runs that share a seed and
    network settings get identical networks and random streams.

    half_life (steps): a broken owner's voice weight decays as
    w * 0.5 ** (steps since breakdown / half_life), so they gradually stop
    talking about it. None = never fades (the committed model)."""
    rng = np.random.default_rng(settings.get("simulation.random_seed", 42))
    h = initialize_households(settings, rng)
    if net_key is not None and net_key in _NET_CACHE:
        graph, edges, state = _NET_CACHE[net_key]
        rng.bit_generator.state = state
    else:
        graph = build_network(h.locations, settings, rng)
        edges = edge_arrays(graph, h.n)
        if net_key is not None:
            _NET_CACHE[net_key] = (graph, edges, rng.bit_generator.state)
    hp = np.zeros((N_STEPS + 1, h.n), dtype=bool)
    br = np.zeros((N_STEPS + 1, h.n), dtype=bool)
    op = np.zeros((N_STEPS + 1, h.n))
    hp[0], br[0], op[0] = h.has_heatpump, h.broken_down, h.opinion
    break_step = np.zeros(h.n)
    for t in range(1, N_STEPS + 1):
        if committed:
            dynamics.opinion_update_step(h, graph, settings, rng)
        else:
            voice = w if half_life is None else w * 0.5 ** ((t - break_step) / half_life)
            was_broken = h.broken_down.copy()
            opinion_update_weighted(h, edges, settings, rng, voice)
            break_step[h.broken_down & ~was_broken] = t
        dynamics.installation_step(h, settings)
        hp[t], br[t], op[t] = h.has_heatpump, h.broken_down, h.opinion
    return h, graph, hp, br, op


@functools.lru_cache(maxsize=1)
def _archetypes():
    return build_archetypes()  # reads the national LSOA table: slow, so once per process


def base_settings(mixing=0.0, seed=1):
    base = Settings.load(PROJECT / "settings.yaml").raw
    cfg = copy.deepcopy(base)
    cfg["world_generation"].update({"seed": seed, "mixing": mixing, "archetypes": copy.deepcopy(_archetypes())})
    # grid, households_per_cell (694) and the spatial_kernel network are as committed
    path = OUT / f"nwom_world_mix{mixing:g}_s{seed}.csv"
    if not path.exists():
        generate_and_write(Settings(cfg), path)
    cfg["households"]["location_source"] = "file"
    cfg["households"]["households_source_file"] = str(path)
    cfg["simulation"]["random_seed"] = seed
    cfg["heatpumps"]["characteristic_gate"] = 0.30
    cfg["heatpumps"]["install_threshold"] = 0.95
    return cfg


def check():
    cfg = base_settings()
    cfg["world_generation"]["households_per_cell"] = 200  # a 3,200-household world keeps the committed loop quick
    path = OUT / "check_world.csv"
    generate_and_write(Settings(cfg), path)
    cfg["households"]["households_source_file"] = str(path)
    s = Settings(cfg)
    t0 = time.time(); _, _, hp_c, br_c, op_c = run(s, 1.0, committed=True); t1 = time.time()
    _, _, hp_v, br_v, op_v = run(s, 1.0); t2 = time.time()
    print(f"committed {t1 - t0:.1f}s, vectorised {t2 - t1:.1f}s")
    print("max |opinion diff|:", np.abs(op_c - op_v).max())
    print("heat pump histories identical:", (hp_c == hp_v).all(), " broken identical:", (br_c == br_v).all())


def time_one():
    s = Settings(base_settings())
    t0 = time.time()
    h, graph, hp, br, _ = run(s, 1.0, net_key="t")
    t1 = time.time()
    run(s, 1.0, net_key="t")
    print(f"n={h.n}, edges={graph.number_of_edges()}, first run {t1 - t0:.1f}s, cached {time.time() - t1:.1f}s")
    print("adoption at checkpoints:", [round(100 * hp[t].mean(), 1) for t in CHECKPOINTS],
          " broken at t100:", round(100 * br[-1].mean(), 1))


WEIGHTS = [1, 2, 3, 5, 10, 20]
BREAKDOWNS = [0.002, 0.005]
LONG_RANGE = [0.1, 0.5]
NOISE = [0.05, 0.10]
SEEDS = [1, 2, 3, 4, 5]


def sweep():
    rows = []
    combos = list(itertools.product(SEEDS, LONG_RANGE, NOISE))
    t0 = time.time()
    for k, (seed, lrf, noise) in enumerate(combos, 1):
        cfg = base_settings(seed=seed)
        cfg["network"]["params"]["long_range_fraction"] = lrf
        cfg["opinions"]["noise_std"] = noise
        runs = [(0.0, 1.0)] + list(itertools.product(BREAKDOWNS, WEIGHTS))
        for br_rate, w in runs:
            c = copy.deepcopy(cfg)
            c["heatpumps"]["breakdown_rate"] = br_rate
            h, _, hp, br, _ = run(Settings(c), float(w), net_key=(seed, lrf))
            eligible = h.characteristic >= 0.30
            row = {"seed": seed, "long_range": lrf, "noise": noise, "breakdown": br_rate, "w": w,
                   "broken_t100": 100 * br[-1].mean()}
            for t in CHECKPOINTS:
                row[f"adopt_t{t}"] = 100 * hp[t].mean()
            # First step at which half of eligible households have adopted.
            frac = hp[:, eligible].mean(axis=1)
            row["t_half_eligible"] = int(np.argmax(frac >= 0.5)) if (frac >= 0.5).any() else np.nan
            rows.append(row)
        print(f"{k}/{len(combos)} scenario-seeds done ({time.time() - t0:.0f}s)", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "nwom_runs.csv", index=False)
    summarise(df)


def summarise(df):
    keys = ["long_range", "noise", "seed"]
    base = df[df["breakdown"] == 0].set_index(keys)
    d = df[df["breakdown"] > 0].copy()
    for t in CHECKPOINTS:
        b = base.loc[pd.MultiIndex.from_frame(d[keys]), f"adopt_t{t}"].to_numpy()
        d[f"short_t{t}"] = 100 * (1 - d[f"adopt_t{t}"] / b)  # % below the no-bad-experience run
    cols = ["broken_t100"] + [f"adopt_t{t}" for t in (25, 50, 100)] + \
           [f"short_t{t}" for t in (25, 50, 100)] + ["t_half_eligible"]
    pd.set_option("display.width", 250, "display.max_columns", 60)
    print("\nBaseline (no bad experiences), mean over seeds:")
    print(base.groupby(["long_range", "noise"])[[f"adopt_t{t}" for t in CHECKPOINTS] + ["t_half_eligible"]]
          .mean().round(1).to_string())
    print("\nWith bad experiences: shortfall = % below baseline at step t (mean over seeds):")
    summ = d.groupby(["long_range", "noise", "breakdown", "w"])[cols].mean()
    summ["short_t50_sd"] = d.groupby(["long_range", "noise", "breakdown", "w"])["short_t50"].std()
    print(summ.round(1).to_string())
    summ.round(2).to_csv(OUT / "nwom_summary.csv")


if __name__ == "__main__":
    {"check": check, "time": time_one, "sweep": sweep,
     "summarise": lambda: summarise(pd.read_csv(OUT / "nwom_runs.csv"))}[sys.argv[1]]()
