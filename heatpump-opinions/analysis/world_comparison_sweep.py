#!/usr/bin/env python3
"""Compare adoption across world files, sweeping simulation seeds.

Built for the `segregated_town` / `mixed_town` pair in examples/worlds/,
which share a generation seed and differ only in `world_generation.mixing`
— a clean gradient of affluence across the town versus neighbourhoods
scattered at random.

The comparison is *paired*: both worlds hold 200 households, so for a given
simulation seed the initial opinion vector and the social network are
identical between them. The only thing that differs is which household sits
where, and therefore who is capable of adopting. That makes a paired test
appropriate and much more sensitive than comparing the groups independently.

What a p-value means here: these are simulation seeds, not sampled people,
so it answers only "is this difference bigger than Monte Carlo noise in my
own model?" — not "is this true of real towns". A difference can be robustly
non-zero here and still be an artefact of the placeholder archetype values.
"""
from __future__ import annotations

import argparse
import copy
import csv
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from heatpump_sim.settings import Settings
from heatpump_sim.simulate import run_simulation

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent
THRESHOLDS = [0.20, 0.50, 0.90]
DEFAULT_WORLDS = [
    PROJECT_ROOT / "examples/worlds/segregated_town.csv",
    PROJECT_ROOT / "examples/worlds/mixed_town.csv",
]


def time_to_threshold(curve: np.ndarray, threshold: float) -> float | None:
    """First timestep at which adoption reaches `threshold`, linearly
    interpolated. None if never reached."""
    above = np.where(curve >= threshold)[0]
    if len(above) == 0:
        return None
    t = int(above[0])
    if t == 0:
        return 0.0
    y0, y1 = curve[t - 1], curve[t]
    frac = (threshold - y0) / (y1 - y0) if y1 != y0 else 0.0
    return (t - 1) + frac


def run_one(world_path: Path, seed: int, base: dict) -> dict:
    cfg = copy.deepcopy(base)
    cfg["households"]["location_source"] = "file"
    cfg["households"]["households_source_file"] = str(world_path)
    cfg["simulation"]["random_seed"] = seed

    result = run_simulation(Settings(cfg))
    curve = result.heatpump_history.mean(axis=1)

    row = {
        "world": world_path.stem,
        "seed": seed,
        "n_households": len(result.locations),
        "final_adoption": float(curve[-1]),
        "total_broken": int(result.broken_history[-1].sum()),
    }
    for th in THRESHOLDS:
        t = time_to_threshold(curve, th)
        row[f"t_to_{int(th * 100)}pct"] = t
        # Whether the threshold was reached at all. Comparing *times* alone
        # conditions on reaching it, which biases the comparison when the
        # worlds differ in how often they get there; this metric does not.
        row[f"reached_{int(th * 100)}pct"] = int(t is not None)

    # Breakdown by descriptive attributes — the payoff of carrying them
    # through from the world file.
    final = result.heatpump_history[-1]
    for attr in ("tenure", "building_type", "lsoa_archetype"):
        values = result.attributes.get(attr)
        if values is None:
            continue
        for level in np.unique(values):
            row[f"adopt_{attr}_{level}"] = float(final[values == level].mean())

    return row, curve


def paired_summary(rows: list[dict], worlds: list[str], metric: str) -> str:
    """Paired comparison of one metric between exactly two worlds."""
    if len(worlds) != 2:
        return ""
    by_seed = {w: {r["seed"]: r[metric] for r in rows if r["world"] == w} for w in worlds}
    seeds = sorted(set(by_seed[worlds[0]]) & set(by_seed[worlds[1]]))
    a = np.array([by_seed[worlds[0]][s] for s in seeds], dtype=float)
    b = np.array([by_seed[worlds[1]][s] for s in seeds], dtype=float)
    valid = ~(np.isnan(a) | np.isnan(b))
    a, b = a[valid], b[valid]
    if len(a) < 2:
        return f"{metric}: too few comparable runs"

    diff = a - b
    mean_diff = diff.mean()
    se = diff.std(ddof=1) / np.sqrt(len(diff))

    try:
        from scipy import stats
        t_stat, p = stats.ttest_rel(a, b)
        crit = stats.t.ppf(0.975, len(diff) - 1)
    except Exception:  # scipy unavailable — fall back to a normal approximation
        p = float("nan")
        crit = 1.96

    lo, hi = mean_diff - crit * se, mean_diff + crit * se
    return (f"  {metric}: {worlds[0]} - {worlds[1]} = {mean_diff:+.4f} "
            f"(95% CI {lo:+.4f} to {hi:+.4f}, n={len(diff)} paired seeds, p={p:.3f})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--worlds", nargs="+", default=[str(p) for p in DEFAULT_WORLDS],
                        help="World files to compare")
    parser.add_argument("--seeds", type=int, default=30, help="Number of simulation seeds per world")
    parser.add_argument("--settings", default=str(PROJECT_ROOT / "settings.yaml"))
    args = parser.parse_args()

    base = yaml.safe_load(open(args.settings))
    worlds = [Path(w) for w in args.worlds]
    for w in worlds:
        if not w.exists():
            raise SystemExit(f"World file not found: {w}")

    rows: list[dict] = []
    curves: dict[str, list[np.ndarray]] = {}

    for world in worlds:
        print(f"Running {world.stem} across {args.seeds} seeds...")
        for seed in range(args.seeds):
            row, curve = run_one(world, seed, base)
            rows.append(row)
            curves.setdefault(world.stem, []).append(curve)

    # Per-run tidy data, for any further analysis.
    all_columns: list[str] = []
    for row in rows:
        for k in row:
            if k not in all_columns:
                all_columns.append(k)
    csv_path = OUT_DIR / "world_comparison.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        writer.writerows(rows)

    np.savez(OUT_DIR / "world_comparison_curves.npz",
             **{name: np.array(c) for name, c in curves.items()})

    # ---- summary ----
    names = [w.stem for w in worlds]
    print("\n" + "=" * 72)
    print(f"WORLD COMPARISON — {args.seeds} simulation seeds per world")
    print("=" * 72)

    headline = ["final_adoption", "total_broken"]
    for t in THRESHOLDS:
        headline += [f"t_to_{int(t*100)}pct", f"reached_{int(t*100)}pct"]
    print(f"\n{'metric':<18}" + "".join(f"{n:>22}" for n in names))
    for metric in headline:
        cells = []
        for n in names:
            vals = np.array([r[metric] for r in rows if r["world"] == n and r[metric] is not None],
                            dtype=float)
            cells.append("never reached" if len(vals) == 0 else f"{vals.mean():.3f} ± {vals.std(ddof=1):.3f}")
        print(f"{metric:<18}" + "".join(f"{c:>22}" for c in cells))
    print("\n(mean ± sd across seeds; times are in timesteps)")

    if len(names) == 2:
        print(f"\nPaired differences ({names[0]} minus {names[1]}):")
        for metric in headline:
            line = paired_summary(rows, names, metric)
            if line:
                print(line)
                if metric.startswith("t_to_") and f"n={args.seeds} paired" not in line:
                    print(f"      ^ fewer than {args.seeds} pairs: this compares timing only among "
                          f"runs that got there.\n"
                          f"        Read it alongside reached_{metric.split('_')[-1]}, which is unbiased.")
        print("\nPairing is meaningful: both worlds have the same household count, so a\n"
              "given seed yields the same initial opinions and the same social network.\n"
              "p-values measure only whether the gap exceeds this model's own Monte Carlo\n"
              "noise — not whether it holds for real towns.")

    # Adoption by tenure, which the descriptive columns make possible.
    tenure_cols = sorted(c for c in all_columns if c.startswith("adopt_tenure_"))
    if tenure_cols:
        print(f"\n{'final adoption by tenure':<28}" + "".join(f"{n:>22}" for n in names))
        for col in tenure_cols:
            cells = []
            for n in names:
                vals = np.array([r[col] for r in rows if r["world"] == n and r.get(col) is not None],
                                dtype=float)
                cells.append(f"{vals.mean():.1%} ± {vals.std(ddof=1):.1%}")
            print(f"  {col.replace('adopt_tenure_', ''):<26}" + "".join(f"{c:>22}" for c in cells))

    plot_path = make_plot(rows, curves, names, tenure_cols)
    print(f"\nPer-run data: {csv_path}")
    print(f"Plot:         {plot_path}")


def make_plot(rows, curves, names, tenure_cols) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {names[0]: "#1f77b4", names[-1]: "#d1495b"}
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

    # 1. Adoption over time, mean with +/-1 sd band.
    ax = axes[0]
    for name in names:
        arr = np.array(curves[name])
        mean, sd = arr.mean(axis=0), arr.std(axis=0, ddof=1)
        t = np.arange(arr.shape[1])
        ax.plot(t, mean, color=colors.get(name), label=name)
        ax.fill_between(t, mean - sd, mean + sd, color=colors.get(name), alpha=0.18, linewidth=0)
    ax.set_xlabel("timestep")
    ax.set_ylabel("adoption fraction")
    ax.set_title("Adoption over time (mean ±1 sd)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    # 2. Paired per-seed differences in final adoption.
    ax2 = axes[1]
    if len(names) == 2:
        by_seed = {n: {r["seed"]: r["final_adoption"] for r in rows if r["world"] == n} for n in names}
        seeds = sorted(set(by_seed[names[0]]) & set(by_seed[names[1]]))
        diff = np.array([by_seed[names[0]][s] - by_seed[names[1]][s] for s in seeds])
        ax2.axhline(0, color="grey", linewidth=1)
        ax2.scatter(range(len(diff)), diff,
                    color=["#1f77b4" if d > 0 else "#d1495b" for d in diff], s=28)
        ax2.axhline(diff.mean(), color="black", linestyle="--", linewidth=1,
                    label=f"mean {diff.mean():+.3f}")
        ax2.set_xlabel("seed (paired)")
        ax2.set_ylabel(f"{names[0]} − {names[1]}")
        ax2.set_title("Paired difference in final adoption")
        ax2.legend(fontsize=8)
        ax2.grid(alpha=0.3)

    # 3. Final adoption by tenure.
    ax3 = axes[2]
    if tenure_cols:
        labels = [c.replace("adopt_tenure_", "") for c in tenure_cols]
        width = 0.8 / len(names)
        for i, name in enumerate(names):
            means = [np.nanmean([r[c] for r in rows if r["world"] == name]) for c in tenure_cols]
            sds = [np.nanstd([r[c] for r in rows if r["world"] == name], ddof=1) for c in tenure_cols]
            pos = np.arange(len(labels)) + i * width - 0.4 + width / 2
            ax3.bar(pos, means, width, yerr=sds, capsize=3, label=name, color=colors.get(name))
        ax3.set_xticks(range(len(labels)))
        ax3.set_xticklabels(labels, rotation=15, ha="right")
        ax3.set_ylabel("final adoption fraction")
        ax3.set_title("Final adoption by tenure")
        ax3.legend(fontsize=8)
        ax3.grid(alpha=0.3, axis="y")

    fig.tight_layout()
    path = OUT_DIR / "world_comparison.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


if __name__ == "__main__":
    main()
