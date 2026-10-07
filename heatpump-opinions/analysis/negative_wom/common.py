"""Shared paths and the six LSOA-type archetypes for the negative word-of-mouth
exploration scripts in this folder.

archetypes.json holds the household-weighted profile of each of Mike's six
LSOA types, so the scripts run without the national LSOA data (which is
gitignored). derive_archetypes() rebuilds it from that data if present:

    python common.py derive
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(PROJECT))

# Generated world files and run outputs; results/ is gitignored.
OUT = PROJECT / "results" / "negative_wom"
OUT.mkdir(parents=True, exist_ok=True)

ARCHETYPES = HERE / "archetypes.json"
TYPE_SLUGS = {0: "t0_mixed_terraced", 1: "t1_city-centre_flats", 2: "t2_suburban_rural_detached",
              3: "t3_social_flats", 4: "t4_social_estates", 5: "t5_urban_owner-occupied_semis"}


def build_archetypes() -> list[dict]:
    return json.loads(ARCHETYPES.read_text())


def weighted_quantile(values, weights, q):
    order = np.argsort(values)
    cum = np.cumsum(weights[order]) / weights.sum()
    return values[order][np.searchsorted(cum, q)]


def derive_archetypes() -> list[dict]:
    import pandas as pd

    from analysis.lsoa_types import load_national
    from data_prep.build_lsoa_table import LSOA_CODE, PROCESSED

    table = load_national()
    types = pd.read_csv(PROCESSED / "lsoa_types_assignments.csv")[[LSOA_CODE, "lsoa_type"]]
    table = table.merge(types, on=LSOA_CODE, validate="one_to_one")
    total = table["n_households"].sum()
    archetypes = []
    for t, g in table.groupby("lsoa_type"):
        w = g["n_households"].to_numpy(dtype=float)
        mean = lambda col: float(np.average(g[col], weights=w))
        dec = g["income_decile"].to_numpy()
        archetypes.append({
            "name": TYPE_SLUGS[t],
            "share": float(w.sum() / total),
            "income_decile_range": [int(weighted_quantile(dec, w, 0.25)),
                                    int(weighted_quantile(dec, w, 0.75))],
            "tenure_mix": {"owner_occupied": mean("prop_owner_occupied"),
                           "private_rented": mean("prop_private_rented"),
                           "social_rented": mean("prop_social_rented")},
            "building_mix": {"detached": mean("prop_detached"),
                             "semi_detached": mean("prop_semi_detached"),
                             "terraced": mean("prop_terraced"),
                             "flat": mean("prop_flats") + mean("prop_caravan")},
        })
    return archetypes


if __name__ == "__main__" and sys.argv[1:] == ["derive"]:
    ARCHETYPES.write_text(json.dumps(derive_archetypes(), indent=1))
