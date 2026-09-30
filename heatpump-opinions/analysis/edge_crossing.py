#!/usr/bin/env python3
"""What share of influence edges cross a cell boundary? A pre-simulation check.

DESIGN.md warns that the arrangement sweep may be close to inert: with a 210 m
distance decay and LSOA-sized cells, nearly all influence may stay inside a
cell. If so, moving the types around the plane changes almost nothing, and the
compute is better spent elsewhere. This script computes the share from the
kernel and the cell geometry alone -- no dynamics.

**Which edges can feel the arrangement.** The graph in DESIGN.md has two kinds
of edge:

- *local* edges, drawn with probability proportional to exp(-d / lambda);
- *long-range* edges, a fraction p rewired to uniformly random targets.

A long-range target is a uniform draw from the whole plane, so the type it
lands in follows the plane's overall type mix *whatever the arrangement*. Only
local edges that cross into a neighbouring cell connect a household to a
neighbour whose type depends on the arrangement. So the share that matters is

    arrangement-sensitive share = (1 - p) * (share of local edges crossing a cell boundary)

and the headline total crossing share, which includes long-range edges, would
overstate how much the sweep can do. (DESIGN.md currently says the arrangement
"can only act through the long-range ties"; by this argument it is the
reverse.)

**Method.** The local crossing share is a property of geometry alone, and is
computed by exact rejection sampling. Draw a household uniformly on the plane
and a displacement from the 2-D exponential kernel -- distance ~ Gamma(2,
lambda), direction uniform -- and discard pairs whose partner falls off the
plane. The accepted pairs are distributed exactly in proportion to the kernel
weight, which is what a globally normalised kernel graph samples edges from.
The mean-degree normalisation cancels out, so mean degree does not enter.

**Cell size from data.** Nesta's property density per LSOA, divided into the
Census household count, gives LSOA areas that sum to 130,311 km2 -- England's
area -- so the implied cell side (sqrt of area) is reported by type and used to
set the sweep. Density uses the Nesta workbook; LSOA boundaries from ONS (OGL)
would give the same areas without it.

**Simplifications.** Households are spread uniformly within and across cells
(real cells vary from roughly 400 to 1,200 households), cells are square and
equal-area, and the plane has hard edges rather than wrapping around.

Usage:
    python -m analysis.edge_crossing
    python -m analysis.edge_crossing --lambdas 100 210 500 --sides 450 600 800 --grid 8
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.lsoa_types import load_national
from data_prep.build_lsoa_table import LSOA_CODE, PROCESSED

# Central values and sweep ranges from DESIGN.md's influence-graph table.
LAMBDAS = [100.0, 210.0, 500.0]          # m; central 210 (Barton-Henry et al. 2021)
LONG_RANGE_FRACTIONS = [0.1, 0.3, 0.5]   # central 0.30 (Liben-Nowell et al. 2005)
DEFAULT_GRID = 8
N_SAMPLES = 2_000_000
SEED = 42


def cell_sides(table: pd.DataFrame) -> pd.DataFrame:
    """Side of a square with each LSOA's area, summarised by type and urban/rural."""
    area_km2 = table["n_households"] / table["property_density_km2"]
    side = 1000 * np.sqrt(area_km2)
    urban = np.where(table["rural_urban_class"].str.startswith("Urban"), "urban", "rural")
    rows = [("England", side), ("England urban", side[urban == "urban"])]
    if "lsoa_type" in table:
        rows += [(f"type {t}", side[table["lsoa_type"] == t])
                 for t in sorted(table["lsoa_type"].unique())]
    return pd.DataFrame([
        {"group": name, "total_area_km2": ((s / 1000) ** 2).sum(),
         "side_p25_m": s.quantile(0.25), "side_median_m": s.median(),
         "side_p75_m": s.quantile(0.75)}
        for name, s in rows
    ])


def local_crossing(grid: int, side: float, lam: float, n: int,
                   rng: np.random.Generator) -> dict[str, float]:
    """Share of kernel-weighted local edges that leave their cell."""
    extent = grid * side
    xi = rng.uniform(0, extent, size=(n, 2))
    r = rng.gamma(shape=2.0, scale=lam, size=n)
    theta = rng.uniform(0, 2 * np.pi, size=n)
    xj = xi + r[:, None] * np.column_stack([np.cos(theta), np.sin(theta)])

    on_plane = ((xj >= 0) & (xj < extent)).all(axis=1)
    ci = np.floor(xi[on_plane] / side).astype(int)
    cj = np.floor(xj[on_plane] / side).astype(int)
    # Chebyshev distance between cells: 0 same cell, 1 adjacent (incl. diagonal).
    hops = np.abs(ci - cj).max(axis=1)
    return {
        "accepted": int(on_plane.sum()),
        "local_cross": float((hops > 0).mean()),
        "local_adjacent": float((hops == 1).mean()),
        "local_beyond_adjacent": float((hops > 1).mean()),
        "mean_edge_m": float(r[on_plane].mean()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--grid", type=int, default=DEFAULT_GRID)
    parser.add_argument("--lambdas", type=float, nargs="+", default=LAMBDAS)
    parser.add_argument("--long-range", type=float, nargs="+", default=LONG_RANGE_FRACTIONS)
    parser.add_argument("--sides", type=float, nargs="+", default=None,
                        help="cell sides in metres (default: quartiles of urban LSOA sides from the data)")
    parser.add_argument("--samples", type=int, default=N_SAMPLES)
    args = parser.parse_args()

    print("Building the national LSOA table...")
    table = load_national()
    assignments_path = PROCESSED / "lsoa_types_assignments.csv"
    if assignments_path.exists():
        types = pd.read_csv(assignments_path)[[LSOA_CODE, "lsoa_type"]]
        table = table.merge(types, on=LSOA_CODE, how="left", validate="one_to_one")
    sides_table = cell_sides(table)

    if args.sides is None:
        urban = sides_table.set_index("group").loc["England urban"]
        sides = [round(urban[c], -1) for c in ("side_p25_m", "side_median_m", "side_p75_m")]
    else:
        sides = args.sides

    rng = np.random.default_rng(SEED)
    same_cell_uniform = 1.0 / args.grid ** 2
    rows = []
    for side in sides:
        for lam in args.lambdas:
            local = local_crossing(args.grid, side, lam, args.samples, rng)
            for p in args.long_range:
                rows.append({
                    "grid": args.grid, "side_m": side, "lambda_m": lam, "long_range_p": p,
                    **local,
                    # Long-range targets are uniform on the plane, so they cross a
                    # boundary unless they happen to land in their own cell.
                    "total_cross": (1 - p) * local["local_cross"] + p * (1 - same_cell_uniform),
                    "arrangement_sensitive": (1 - p) * local["local_cross"],
                })
    result = pd.DataFrame(rows)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    sides_table.round(1).to_csv(PROCESSED / "edge_crossing_cell_sides.csv", index=False)
    result.round(4).to_csv(PROCESSED / "edge_crossing.csv", index=False)

    pd.set_option("display.width", 200, "display.max_columns", 50)
    print("\n--- Implied LSOA cell side (m) ---")
    print(sides_table.round(0).to_string(index=False))
    print(f"\n--- Local edges crossing a cell boundary ({args.grid}x{args.grid} plane) ---")
    local_view = result.drop_duplicates(["side_m", "lambda_m"])[
        ["side_m", "lambda_m", "mean_edge_m", "local_cross", "local_adjacent", "local_beyond_adjacent"]]
    print(local_view.round(3).to_string(index=False))
    print("\n--- Arrangement-sensitive share = (1 - p) * local_cross; total includes long-range ---")
    pivot = result.pivot_table(index=["side_m", "lambda_m"], columns="long_range_p",
                               values=["arrangement_sensitive", "total_cross"])
    print(pivot.round(3).to_string())
    print(f"\nWrote 2 CSVs to {PROCESSED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
