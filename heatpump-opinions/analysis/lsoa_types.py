#!/usr/bin/env python3
"""Cluster England's LSOAs into a handful of types, for the stylised plane.

The stylised-plane design replaces real geography with a grid whose cells are
LSOA *types*, so that spatial arrangement becomes something we sweep rather
than something we inherit from one town. That needs a defensible answer to
"what types, and how common is each?". This script is that answer.

Three deliberate choices, all in the service of being easy to justify:

1. **Cluster on the model's own gate variables, nothing else.** A type is only
   meaningful here insofar as it changes the joint distribution of the gates
   in DESIGN.md -- decision right (tenure), capability (dwelling), opportunity
   (income). Clustering on a wider set of census variables would produce a
   general-purpose geodemographic classification, which is a different and
   less relevant object. The variables below ARE the model's inputs.

2. **k-means, written out in numpy.** No new dependency, and the whole method
   is visible in this file rather than behind a library call. For an audience
   that has to be persuaded, that is worth more than a faster implementation.

3. **Stability guards the choice of k; it does not make it.** We resample
   LSOAs, recluster, and ask how reliably each cluster reproduces (Hennig's
   Jaccard criterion: >0.75 stable, <0.6 not a real cluster). Run on England,
   *every* k from 2 to 10 clears 0.85 -- at n=33,755 a bootstrap barely moves
   a centroid, so a high score on its own says little. `--null-check` is
   therefore the test that carries the weight: it reruns the same measure on
   a Gaussian with the same mean and covariance but no clusters by
   construction. The real data beats that null at k=3 (0.99 vs 0.69) and k=6
   (0.97 vs 0.81), but only barely at k=4 (0.99 vs 0.97) -- a structureless
   ellipsoid also cuts stably into four. So the honest reading is that the
   partition is reproducible and not an artefact, while the *number* of types
   is a modelling judgement: the smallest k that separates the situations the
   model treats differently. Inertia falls smoothly with no clear elbow, which
   says the same thing from the other direction.

The types are used to ARRANGE the plane. The data on it should come from
sampling real LSOAs within a type, not from the type centroid -- that keeps
the empirical joint distribution and the within-type spread that makes
capability vary between neighbours. See the profile output's `sd_` columns
for how much spread that is.

Usage:
    python -m analysis.lsoa_types            # diagnostics + profiles at DEFAULT_K
    python -m analysis.lsoa_types --k 6      # profile a specific k
    python -m analysis.lsoa_types --k-range 2 12
    python -m analysis.lsoa_types --null-check   # real vs no-structure null
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_prep.build_lsoa_table import LSOA_CODE, PROCESSED, build
from data_prep.sources import STUDY_AREAS

# One variable per gate, with the redundant category of each composition
# dropped. Tenure proportions sum to 1, so owner-occupied is implied by the
# other two; dwelling proportions sum to 1, so terraced (plus the negligible
# caravan share) is implied by the other three. Keeping every category would
# make the covariance singular and silently double-weight composition against
# income.
GATE_VARIABLES = {
    "prop_social_rented": "decision right",
    "prop_private_rented": "decision right",
    "prop_flats": "capability",
    "prop_detached": "capability",
    "prop_semi_detached": "capability",
    "income_score": "opportunity",
}

# Reported in the profiles but NOT clustered on: these describe the types,
# they do not define them.
PROFILE_ONLY = ["prop_owner_occupied", "prop_terraced", "income_decile", "imd_decile"]

DEFAULT_K = 6
N_RESTARTS = 20
N_BOOTSTRAP = 50
SEED = 42

# Hennig's rule of thumb for bootstrapped cluster stability.
STABLE = 0.75
UNSTABLE = 0.60


# --- k-means -----------------------------------------------------------------

def _sqdist(x: np.ndarray, centres: np.ndarray) -> np.ndarray:
    """Squared distances, via |x|^2 - 2x.c + |c|^2.

    Algebraically identical to the obvious broadcast form, but it is a matrix
    multiply rather than an n x k x d temporary -- which is the difference
    between this script running in a minute and running in half an hour.
    """
    return ((x ** 2).sum(1)[:, None] - 2 * x @ centres.T + (centres ** 2).sum(1)[None, :])


def _kmeans_plusplus(x: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """Seed centroids far apart, so restarts explore genuinely different fits."""
    centres = [x[rng.integers(len(x))]]
    for _ in range(k - 1):
        d2 = np.maximum(_sqdist(x, np.array(centres)).min(axis=1), 0)
        total = d2.sum()
        # Degenerate case: fewer distinct points than k. Fall back to uniform.
        probabilities = d2 / total if total > 0 else np.full(len(x), 1 / len(x))
        centres.append(x[rng.choice(len(x), p=probabilities)])
    return np.array(centres)


def _fit_once(x: np.ndarray, k: int, rng: np.random.Generator, max_iter: int = 300):
    centres = _kmeans_plusplus(x, k, rng)
    labels = np.zeros(len(x), dtype=int)
    for _ in range(max_iter):
        distances = _sqdist(x, centres)
        new_labels = distances.argmin(axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for j in range(k):
            member = x[labels == j]
            # An emptied cluster is re-seeded on the worst-fit point rather
            # than left to collapse, which would quietly return fewer than k.
            centres[j] = member.mean(0) if len(member) else x[distances.min(1).argmax()]
    inertia = ((x - centres[labels]) ** 2).sum()
    return labels, centres, inertia


def kmeans(x: np.ndarray, k: int, seed: int, n_restarts: int = N_RESTARTS):
    """Best of `n_restarts` k-means fits, by inertia."""
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(n_restarts):
        result = _fit_once(x, k, rng)
        if best is None or result[2] < best[2]:
            best = result
    assert best is not None
    return best


def _assign(x: np.ndarray, centres: np.ndarray) -> np.ndarray:
    return _sqdist(x, centres).argmin(axis=1)


# --- stability ---------------------------------------------------------------

def bootstrap_stability(x: np.ndarray, labels: np.ndarray, k: int, seed: int,
                        n_bootstrap: int = N_BOOTSTRAP) -> np.ndarray:
    """Per-cluster mean Jaccard similarity under resampling.

    Resample LSOAs with replacement, recluster, then assign *all* original
    LSOAs to the bootstrap centroids. For each original cluster, find the
    bootstrap cluster it most overlaps with and record the Jaccard index.
    A cluster that keeps reappearing under resampling is a real feature of
    the data; one that does not is an artefact of where the boundaries fell.
    """
    rng = np.random.default_rng(seed)
    scores = np.zeros((n_bootstrap, k))
    original = [labels == j for j in range(k)]
    for b in range(n_bootstrap):
        sample = rng.integers(0, len(x), len(x))
        _, centres, _ = kmeans(x[sample], k, seed=int(rng.integers(1 << 31)), n_restarts=5)
        resampled = _assign(x, centres)
        for j in range(k):
            a = original[j]
            best = 0.0
            for m in range(k):
                bm = resampled == m
                union = (a | bm).sum()
                if union:
                    best = max(best, float((a & bm).sum()) / union)
            scores[b, j] = best
    return scores.mean(axis=0)


def null_check(x: np.ndarray, k_values: tuple[int, ...], seed: int = SEED) -> pd.DataFrame:
    """Stability on the real data vs. a same-covariance Gaussian with no clusters.

    The comparison, not the absolute score, is what tells us the partition
    reflects structure in England's housing stock rather than the geometry of
    cutting any large cloud into k pieces.
    """
    rng = np.random.default_rng(seed)
    null = rng.multivariate_normal(x.mean(0), np.cov(x, rowvar=False), size=len(x))
    rows = []
    for k in k_values:
        scores = {}
        for name, data in (("real", x), ("null", null)):
            labels, _, _ = kmeans(data, k, seed=seed)
            scores[name] = bootstrap_stability(data, labels, k, seed=seed, n_bootstrap=20)
        rows.append({
            "k": k,
            "real_mean_jaccard": scores["real"].mean(),
            "null_mean_jaccard": scores["null"].mean(),
            "gap": scores["real"].mean() - scores["null"].mean(),
        })
        print(f"  k={k:2d}  real={rows[-1]['real_mean_jaccard']:.3f}  "
              f"null={rows[-1]['null_mean_jaccard']:.3f}  "
              f"gap={rows[-1]['gap']:+.3f}")
    return pd.DataFrame(rows)


# --- reporting ---------------------------------------------------------------

def load_national() -> pd.DataFrame:
    table = build(study_areas_only=False)
    # IMD 2025 is England-only, and the merges are inner joins, so the table is
    # already England. Assert it rather than assume it.
    assert table[LSOA_CODE].str.startswith("E01").all(), "Expected England-only LSOAs"
    return table


def standardise(table: pd.DataFrame) -> np.ndarray:
    x = table[list(GATE_VARIABLES)].to_numpy(dtype=float)
    return (x - x.mean(0)) / x.std(0)


def diagnostics(x: np.ndarray, k_range: range) -> pd.DataFrame:
    rows = []
    for k in k_range:
        labels, _, inertia = kmeans(x, k, seed=SEED)
        stability = bootstrap_stability(x, labels, k, seed=SEED)
        rows.append({
            "k": k,
            "inertia": inertia,
            "mean_jaccard": stability.mean(),
            "min_jaccard": stability.min(),
            "n_stable": int((stability >= STABLE).sum()),
            "n_unstable": int((stability < UNSTABLE).sum()),
            "smallest_cluster_pct": 100 * np.bincount(labels, minlength=k).min() / len(labels),
        })
        print(f"  k={k:2d}  inertia={inertia:9.0f}  "
              f"mean Jaccard={stability.mean():.2f}  min={stability.min():.2f}  "
              f"stable={rows[-1]['n_stable']}/{k}")
    return pd.DataFrame(rows)


def profile(table: pd.DataFrame, labels: np.ndarray, stability: np.ndarray) -> pd.DataFrame:
    table = table.assign(lsoa_type=labels)
    total_households = table["n_households"].sum()
    rows = []
    for j, group in table.groupby("lsoa_type"):
        row = {
            "lsoa_type": j,
            "n_lsoas": len(group),
            "pct_lsoas": 100 * len(group) / len(table),
            "pct_households": 100 * group["n_households"].sum() / total_households,
            "jaccard": stability[j],
        }
        for variable in list(GATE_VARIABLES) + PROFILE_ONLY:
            row[f"mean_{variable}"] = group[variable].mean()
        # Within-type spread matters as much as the mean: it is what makes
        # capability vary between neighbours once households are drawn.
        for variable in GATE_VARIABLES:
            row[f"sd_{variable}"] = group[variable].std()
        row["pct_urban"] = 100 * group["rural_urban_class"].str.startswith("Urban").mean()
        rows.append(row)
    return pd.DataFrame(rows)


def study_town_composition(table: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """Where Derby and Nottingham sit in the typology.

    Not used to build anything -- it is the check that the types are relevant
    to the towns already analysed, and the basis for calibrating the plane's
    arrangement parameter against a real place.
    """
    town = table["lad_code"].map({v: k for k, v in STUDY_AREAS.items()})
    subset = table.assign(lsoa_type=labels, town=town)
    subset = subset[subset["town"].notna()]
    counts = pd.crosstab(subset["town"], subset["lsoa_type"])
    return 100 * counts.div(counts.sum(axis=1), axis=0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--k-range", type=int, nargs=2, default=[2, 10],
                        metavar=("LO", "HI"))
    parser.add_argument("--null-check", action="store_true",
                        help="compare stability against a no-structure null and exit")
    args = parser.parse_args()

    print("Building the national LSOA table...")
    table = load_national()
    x = standardise(table)
    print(f"{len(table):,} England LSOAs, {x.shape[1]} clustering variables:")
    for variable, gate in GATE_VARIABLES.items():
        print(f"  {variable:24s} <- {gate}")

    if args.null_check:
        print("\nReal vs no-structure null (20 bootstraps each):")
        null_check(x, (3, 4, 6, 8)).to_csv(PROCESSED / "lsoa_types_null_check.csv", index=False)
        return 0

    print("\nStability across k (50 bootstraps each):")
    diag = diagnostics(x, range(args.k_range[0], args.k_range[1] + 1))

    print(f"\nProfiling k={args.k}:")
    labels, _, _ = kmeans(x, args.k, seed=SEED)
    stability = bootstrap_stability(x, labels, args.k, seed=SEED)
    profiles = profile(table, labels, stability)
    composition = study_town_composition(table, labels)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    diag.to_csv(PROCESSED / "lsoa_types_diagnostics.csv", index=False)
    profiles.to_csv(PROCESSED / "lsoa_types_profiles.csv", index=False)
    composition.to_csv(PROCESSED / "lsoa_types_study_towns.csv")
    table.assign(lsoa_type=labels)[[LSOA_CODE, "lsoa_name", "lad_name", "lsoa_type"]].to_csv(
        PROCESSED / "lsoa_types_assignments.csv", index=False)

    pd.set_option("display.width", 200, "display.max_columns", 50)
    print("\n--- Type profiles (means) ---")
    print(profiles[["lsoa_type", "n_lsoas", "pct_lsoas", "pct_households", "jaccard",
                    *[f"mean_{v}" for v in GATE_VARIABLES], "pct_urban"]]
          .round(3).to_string(index=False))
    print("\n--- Within-type spread (sd) ---")
    print(profiles[["lsoa_type", *[f"sd_{v}" for v in GATE_VARIABLES]]]
          .round(3).to_string(index=False))
    print("\n--- Study towns: % of their LSOAs in each type ---")
    print(composition.round(1).to_string())
    print(f"\nWrote 4 CSVs to {PROCESSED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
