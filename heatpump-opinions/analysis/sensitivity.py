#!/usr/bin/env python3
"""One-at-a-time sensitivity analysis of the headline results.

Each assumption is moved to a low and a high value (or, for switches, to its
alternative) with everything else at its settings.yaml default. Every variant
is run as a pair, with no dissatisfied owners and with `--share` of new owners
dissatisfied and complaining for ever, sharing the network and random
numbers within a seed so the difference between the pair is the effect of
dissatisfaction alone. Three measures per pair:

    pace     adoption at 10 years with no dissatisfaction (% of households)
    lost     heat-pump-years lost over 25 years to dissatisfaction (%)
    equity   % loss at 25 years for social flats over the % loss for
             suburban/rural detached homes (>1 = the type already behind is
             hit harder). Social flats are ~6% of households, so their loss
             is noisy run to run: equity is the ratio of the two types'
             losses averaged over seeds, never a per-run ratio. Where too few
             social flats are eligible to measure (e.g. a high capability
             gate) it is missing.

The low/high values are judgement calls, not estimates: roughly halving and
doubling rates, ±0.05 on quantities that sit on a 0-1 motivation scale, and
the briefing's sweep ranges for the network. They show which assumptions the
results lean on, not how uncertain they are.

    python analysis/sensitivity.py --seeds 5 --jobs 5
    python analysis/sensitivity.py --plot-only

Writes results/sensitivity/sensitivity_runs.csv and sensitivity.png.
"""
from __future__ import annotations

import argparse
import copy
import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from heatpump_sim.agents import Population  # noqa: E402
from heatpump_sim.dynamics import adoption_params  # noqa: E402
from heatpump_sim.metrics import adoption_by_type  # noqa: E402
from heatpump_sim.network import build_network, rewire_preserving_degree  # noqa: E402
from heatpump_sim.settings import Settings  # noqa: E402
from heatpump_sim.simulate import building_type_codes, run_dynamics  # noqa: E402
from heatpump_sim.worldgen import generate_world  # noqa: E402

OUT = PROJECT / "results" / "sensitivity"
MONTHS = 300
BEHIND, AHEAD = "t3_social_flats", "t2_suburban_rural_detached"

# (label, settings path, values). "world.mixing" regenerates the world; the
# world seed is fixed, so households sit at the same coordinates throughout.
PARAMS = [
    ("Trigger rate (/month)", "adoption.trigger_rate", [1 / 240, 1 / 120], ["1/240", "1/120"]),
    ("Motivation memory", "motivation.memory", [0.025, 0.10], None),
    ("Message strength", "word_of_mouth.message_strength", [0.04, 0.09], None),
    ("Contact rate", "word_of_mouth.contact_rate", [0.5, 0.9], None),
    ("Baseline motivation", "motivation.baseline_mean", [0.25, 0.35], None),
    ("Adoption half-point", "adoption.half_point", [0.75, 0.85], None),
    ("Adoption slope", "adoption.slope", [0.05, 0.10], None),
    ("Capability gate", "adoption.capability_gate", [0.15, 0.45], None),
    ("Complaint duration (months)", "dissatisfaction.duration_months", [12, 60], None),
    ("Complaint weight", "dissatisfaction.weight", [0.5, 3.0], None),
    ("Contacts per household", "network.params.mean_degree", [8, 20], None),
    ("Decay length (m)", "network.params.decay_length_m", [100, 500], None),
    ("Long-range share", "network.params.long_range_fraction", [0.1, 0.5], None),
    ("Town segregation (mixing)", "world_generation.mixing", [0.0, 1.0], None),
    ("Network rewired", "network.rewire", [True], ["rewired"]),
    ("First owners", "adoption.initial_owners", ["random"], ["random"]),
]
NETWORK_KEYS = ("network.", "world_generation.")


def set_path(cfg: dict, path: str, value) -> None:
    *parents, leaf = path.split(".")
    node = cfg
    for p in parents:
        node = node.setdefault(p, {})
    node[leaf] = value


def get_path(cfg: dict, path: str):
    node = cfg
    for p in path.split("."):
        node = node[p]
    return node


def variants() -> list[tuple[str, str, object, str]]:
    """(parameter label, path, value, value label); the default first."""
    out = [("Default", "", None, "default")]
    for label, path, values, names in PARAMS:
        for i, v in enumerate(values):
            out.append((label, path, v, names[i] if names else f"{v:g}"))
    return out


def measures(owner_0: np.ndarray, owner_q: np.ndarray, eligible: np.ndarray, types: np.ndarray) -> dict:
    """The three measures from a no-dissatisfaction / dissatisfaction pair."""
    lost = 100 * (1 - owner_q.mean(axis=1).sum() / owner_0.mean(axis=1).sum())
    by0 = adoption_by_type(owner_0[-1], eligible, types)
    byq = adoption_by_type(owner_q[-1], eligible, types)
    loss = {t: 100 * (1 - byq[t] / by0[t]) if t in by0 and by0[t] > 0 else float("nan") for t in (BEHIND, AHEAD)}
    return {"pace": 100 * owner_0[120].mean(), "adoption_25y": 100 * owner_0[-1].mean(),
            "adoption_25y_q": 100 * owner_q[-1].mean(), "lost": lost,
            "loss_behind": loss[BEHIND], "loss_ahead": loss[AHEAD]}


def run_seed(seed: int, base: dict, share: float) -> list[dict]:
    """All variants for one seed, reusing a population and network wherever
    the variant does not change them."""
    worlds, networks, rows = {}, {}, []
    for label, path, value, value_label in variants():
        cfg = copy.deepcopy(base)
        if path:
            set_path(cfg, path, value)
        mixing = get_path(cfg, "world_generation.mixing")
        if mixing not in worlds:
            w = generate_world(Settings(cfg))
            worlds[mixing] = Population(w["locations"], w["characteristic"], w["attributes"])
        pop = worlds[mixing]

        net_key = (mixing, repr(get_path(cfg, "network")))
        if net_key not in networks:
            rng = np.random.default_rng(seed)
            s = Settings(cfg)
            g = build_network(pop.locations, s, rng)
            if s.get("network.rewire", False):
                g = rewire_preserving_degree(g, rng)
            networks[net_key] = (np.array(list(g.edges()), dtype=np.int64).reshape(-1, 2), rng.bit_generator.state)
        edges, state = networks[net_key]

        owners, eligible = [], None
        for q in (0.0, share):
            c = copy.deepcopy(cfg)
            c["dissatisfaction"]["share"] = q
            rng = np.random.default_rng()
            rng.bit_generator.state = copy.deepcopy(state)
            h = run_dynamics(pop.characteristic, edges, building_type_codes(pop.attributes),
                             adoption_params(Settings(c)), rng, months=MONTHS)
            owners.append(h.owner)
            eligible = h.eligible
        rows.append({"seed": seed, "parameter": label, "value": value_label,
                     **measures(owners[0], owners[1], eligible, np.asarray(pop.attributes["lsoa_archetype"]))})
    return rows


METRICS = [("pace", "Pace: adoption at 10 years,\nnone dissatisfied (%)"),
           ("lost", "Headline: heat-pump-years lost\nover 25 years (%)"),
           ("equity", "Equity: social flats' loss over\nsuburban detached homes' loss (×)")]


def plot(csv_path: Path, out_path: Path, share: float) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = list(csv.DictReader(open(csv_path)))
    for r in rows:
        for k in ("pace", "lost", "loss_behind", "loss_ahead"):
            r[k] = float(r[k])
    INK, INK2, GRID, SURF = "#1a1a19", "#52514e", "#e4e3dd", "#fcfcfb"
    LOW, HIGH = "#2a78d6", "#eb6834"
    plt.rcParams.update({"font.size": 9, "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.edgecolor": GRID, "figure.facecolor": SURF,
                         "axes.facecolor": SURF, "axes.titlesize": 9.5, "axes.titleweight": "bold",
                         "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False})

    def mean(param, value, metric):
        """Mean over seeds and the half-width of its 95% interval (none for
        equity, a ratio of means)."""
        sel = [r for r in rows if r["parameter"] == param and r["value"] == value]
        if metric == "equity":
            behind = np.array([r["loss_behind"] for r in sel])
            ahead = np.array([r["loss_ahead"] for r in sel])
            if np.isnan(behind).all() or np.nanmean(ahead) <= 0:
                return float("nan"), 0.0
            return float(np.nanmean(behind) / np.nanmean(ahead)), 0.0
        vals = np.array([r[metric] for r in sel])
        half = 1.96 * vals.std(ddof=1) / np.sqrt(len(vals)) if len(vals) > 1 else 0.0
        return float(vals.mean()), float(half)

    labels = [p[0] for p in PARAMS]
    values = {p[0]: (p[3] if p[3] else [f"{v:g}" for v in p[2]]) for p in PARAMS}
    base_lost = mean("Default", "default", "lost")[0]
    swing = {lab: max(abs(mean(lab, v, "lost")[0] - base_lost) for v in values[lab]) for lab in labels}
    order = sorted(labels, key=lambda lab: swing[lab])  # largest headline swing at the top

    fig, axes = plt.subplots(1, 3, figsize=(13, 0.42 * len(order) + 1.6), sharey=True,
                             gridspec_kw={"wspace": 0.08})
    for ax, (metric, title) in zip(axes, METRICS):
        b, bsd = mean("Default", "default", metric)
        ax.axvspan(b - bsd, b + bsd, color=GRID, alpha=0.6, lw=0)
        ax.axvline(b, color=INK, lw=1)
        for y, lab in enumerate(order):
            pts = [(v, *mean(lab, v, metric)) for v in values[lab]]
            pts = [p for p in pts if not np.isnan(p[1])]
            if not pts:
                ax.text(b, y, "not measurable", ha="center", va="center", fontsize=7, color=INK2)
                continue
            xs = [p[1] for p in pts]
            ax.plot([min(xs + [b]), max(xs + [b])], [y, y], color=GRID, lw=3, zorder=1, solid_capstyle="round")
            for i, (v, m, _) in enumerate(pts):
                colour = HIGH if (len(values[lab]) == 2 and v == values[lab][1]) else LOW
                ax.scatter(m, y, s=42, color=colour, edgecolor=SURF, linewidth=1.2, zorder=3)
                if metric == "lost":
                    above = colour == LOW  # low labels above the point, high labels below
                    ax.annotate(v, (m, y), xytext=(0, 6 if above else -7), textcoords="offset points",
                                ha="center", va="bottom" if above else "top", fontsize=7, color=INK2)
        ax.set_title(title, pad=8)
        ax.grid(axis="x", color=GRID, lw=0.5)
    axes[0].set_yticks(range(len(order)), order)
    axes[0].set_ylim(-0.6, len(order) - 0.3)
    for ax in axes[1:]:
        ax.tick_params(axis="y", length=0)
    fig.suptitle(f"One-at-a-time sensitivity, {int(share * 100)}% of new owners dissatisfied, complaints for ever. "
                 "Black line and band: default and its 95% interval over seeds. Blue: low (or alternative) value; "
                 "orange: high value", x=0.01, ha="left", fontsize=8.5, color=INK2, y=1.0)
    fig.savefig(out_path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--jobs", type=int, default=1, help="Seeds to run in parallel (~1 GB each)")
    parser.add_argument("--share", type=float, default=0.1, help="Share of new owners dissatisfied")
    parser.add_argument("--settings", default=str(PROJECT / "settings.yaml"))
    parser.add_argument("--plot-only", action="store_true", help="Redraw the figure from the saved CSV")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "sensitivity_runs.csv"

    if not args.plot_only:
        base = Settings.load(args.settings).raw
        base["dissatisfaction"]["duration_months"] = None  # complaints for ever unless a variant says otherwise
        seeds = list(range(1, args.seeds + 1))
        t0 = time.time()
        rows = []
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            for seed_rows in pool.map(run_seed, seeds, [base] * len(seeds), [args.share] * len(seeds)):
                rows += seed_rows
                print(f"seed {seed_rows[0]['seed']} done ({time.time() - t0:.0f}s)", flush=True)
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    plot(csv_path, OUT / "sensitivity.png", args.share)
    print(f"Runs: {csv_path}\nFigure: {OUT / 'sensitivity.png'}")


if __name__ == "__main__":
    main()
