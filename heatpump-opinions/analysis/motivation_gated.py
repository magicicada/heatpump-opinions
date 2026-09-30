#!/usr/bin/env python3
"""How many households are gated only by motivation? A pre-simulation check.

DESIGN.md asks for this before any dynamics are run: word of mouth acts on
motivation alone, so the households it can immediately reach are those for
whom motivation is the only gate left standing. If that population is small,
that is a cheap and important finding.

Under the three-channel model in DESIGN.md:

- **Social tenants in houses** are the motivation-only population. The landlord
  funds the install, handles suitability and sets the timing, so the tenant's
  consent -- motivation -- is the gate that remains.
- **Social tenants in flats** are also gated by capability: two thirds of the
  social-flats type live in flats, where a heat pump often is not feasible.
- **Private renters** are gated by a landlord who rarely initiates at all.
- **Owner-occupiers in houses** are gated by motivation *plus* opportunity and a
  trigger (boiler failure). Word of mouth delays them rather than losing them,
  so they are reported separately and not counted in the headline.
- **Owner-occupiers in flats** are gated by capability.

"House" means detached, semi-detached or terraced; flats and the negligible
caravan share are treated as capability-gated.

The one real difficulty: the Census tables we hold give tenure (TS054) and
dwelling type (TS044) *separately* per LSOA, not jointly. So the number of
social tenants in houses in an LSOA is not observed. Two answers are given:

1. **Independence estimate** -- tenure and dwelling type drawn independently
   within each LSOA. This is also what a naive household expansion would do.
   Social tenants are more likely than their neighbours to live in flats, so
   this probably *overstates* social-in-houses.
2. **Frechet bounds** -- the smallest and largest counts consistent with the
   two margins in each LSOA, summed. These make no assumption at all, and the
   truth lies between them.

A Census tenure-by-accommodation cross-tabulation at LSOA level would replace
both with the observed figure, if one is published.

Usage:
    python -m analysis.motivation_gated
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.lsoa_types import load_national
from data_prep.build_lsoa_table import LSOA_CODE, PROCESSED
from data_prep.sources import STUDY_AREAS

TYPE_NAMES = {
    0: "Mixed terraced, private-rented",
    1: "City-centre flats, private-rented",
    2: "Suburban/rural detached",
    3: "Social flats",
    4: "Social estates - houses",
    5: "Urban owner-occupied semis",
}


def household_counts(table: pd.DataFrame) -> pd.DataFrame:
    """Per-LSOA household counts in each tenure x dwelling cell.

    Proportions come from each Census table against its own total and are
    scaled by TS041, matching build_lsoa_table (the tables do not reconcile
    exactly because of disclosure control).
    """
    n = table["n_households"].to_numpy(dtype=float)
    social = table["prop_social_rented"].to_numpy()
    private = table["prop_private_rented"].to_numpy()
    owner = table["prop_owner_occupied"].to_numpy()
    house = (table["prop_detached"] + table["prop_semi_detached"] + table["prop_terraced"]).to_numpy()
    flat = 1.0 - house

    return pd.DataFrame({
        LSOA_CODE: table[LSOA_CODE],
        "n_households": n,
        "social_rented": n * social,
        # Independence estimate and Frechet bounds for social tenants in houses.
        "social_house": n * social * house,
        "social_house_lo": n * np.maximum(0.0, social + house - 1.0),
        "social_house_hi": n * np.minimum(social, house),
        "social_flat": n * social * flat,
        "private_rented": n * private,
        "owner_house": n * owner * house,
        "owner_house_lo": n * np.maximum(0.0, owner + house - 1.0),
        "owner_house_hi": n * np.minimum(owner, house),
        "owner_flat": n * owner * flat,
    })


def summarise(counts: pd.DataFrame, group: pd.Series | None, label: str) -> pd.DataFrame:
    """Percentages of households in each gate category, per group."""
    keyed = counts.assign(group=label if group is None else group.to_numpy())
    sums = keyed.drop(columns=LSOA_CODE).groupby("group").sum()
    out = pd.DataFrame(index=sums.index)
    out["households"] = sums["n_households"].round().astype(int)
    for column in ("social_house", "social_house_lo", "social_house_hi", "social_flat",
                   "private_rented", "owner_house", "owner_house_lo", "owner_house_hi",
                   "owner_flat"):
        out[f"pct_{column}"] = 100 * sums[column] / sums["n_households"]
    # Of the social renters in the group, how many are in houses: the share of
    # the social channel that motivation alone governs.
    out["pct_of_social_in_houses"] = 100 * sums["social_house"] / sums["social_rented"]
    return out


def main() -> int:
    print("Building the national LSOA table...")
    table = load_national()
    counts = household_counts(table)

    assignments_path = PROCESSED / "lsoa_types_assignments.csv"
    if not assignments_path.exists():
        print(f"{assignments_path} not found -- run `python -m analysis.lsoa_types` first.")
        return 1
    types = pd.read_csv(assignments_path)[[LSOA_CODE, "lsoa_type"]]
    table = table.merge(types, on=LSOA_CODE, how="left", validate="one_to_one")
    if table["lsoa_type"].isna().any():
        print("Some LSOAs have no type assignment -- rerun `python -m analysis.lsoa_types`.")
        return 1

    town = table["lad_code"].map({v: k for k, v in STUDY_AREAS.items()})
    in_town = town.notna().to_numpy()

    result = pd.concat([
        summarise(counts, None, "England"),
        summarise(counts, table["lsoa_type"].map(TYPE_NAMES), "type"),
        summarise(counts[in_town].reset_index(drop=True),
                  town[in_town].reset_index(drop=True), "town"),
    ])

    # Where the motivation-only population lives: share of England's social
    # tenants in houses held by each type. The typology localises the diagnostic
    # but does not contain it (DESIGN.md), and this says by how much.
    by_type = counts.groupby(table["lsoa_type"].map(TYPE_NAMES).to_numpy())["social_house"].sum()
    location = (100 * by_type / by_type.sum()).rename("pct_of_england_social_in_houses")

    PROCESSED.mkdir(parents=True, exist_ok=True)
    result.round(2).to_csv(PROCESSED / "motivation_gated.csv", index_label="group")
    location.round(2).to_csv(PROCESSED / "motivation_gated_location.csv", index_label="lsoa_type")

    pd.set_option("display.width", 200, "display.max_columns", 50)
    print("\n--- % of households by gate category ---")
    print("social_house = motivation-only (headline); lo/hi = Frechet bounds, no assumption")
    print(result.round(1).to_string())
    print("\n--- Where England's social tenants in houses live (independence estimate) ---")
    print(location.round(1).sort_values(ascending=False).to_string())
    print(f"\nWrote 2 CSVs to {PROCESSED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
