#!/usr/bin/env python3
"""Derive the world-generation archetypes from the six LSOA types.

Each archetype is the household-weighted profile of one LSOA type: its share
of England's households, its 25th-75th percentile income decile, and its mean
tenure and building-type mix. Prints the `archetypes:` block for
settings.yaml. Needs the national LSOA table and type assignments:

    python -m data_prep.download
    python -m data_prep.build_lsoa_table
    python analysis/lsoa_types.py
    python analysis/derive_archetypes.py

Written by Michael Fell as analysis/negative_wom/common.py (Oct 2026).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.lsoa_types import load_national  # noqa: E402
from data_prep.build_lsoa_table import LSOA_CODE, PROCESSED  # noqa: E402

TYPE_SLUGS = {0: "t0_mixed_terraced", 1: "t1_city-centre_flats", 2: "t2_suburban_rural_detached",
              3: "t3_social_flats", 4: "t4_social_estates", 5: "t5_urban_owner-occupied_semis"}


def weighted_quantile(values, weights, q):
    order = np.argsort(values)
    cum = np.cumsum(weights[order]) / weights.sum()
    return values[order][np.searchsorted(cum, q)]


def derive_archetypes() -> list[dict]:
    table = load_national()
    types = pd.read_csv(PROCESSED / "lsoa_types_assignments.csv")[[LSOA_CODE, "lsoa_type"]]
    table = table.merge(types, on=LSOA_CODE, validate="one_to_one")
    total = table["n_households"].sum()
    archetypes = []
    for t, g in table.groupby("lsoa_type"):
        w = g["n_households"].to_numpy(dtype=float)
        mean = lambda col: float(np.average(g[col], weights=w))  # noqa: E731
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


def as_yaml(archetypes: list[dict]) -> str:
    """The settings.yaml block, at full precision so worlds are reproducible."""
    fmt = lambda d: "{" + ", ".join(f"{k}: {v!r}" for k, v in d.items()) + "}"  # noqa: E731
    lines = ["  archetypes:"]
    for a in archetypes:
        lines += [f"    - name: {a['name']}",
                  f"      share: {a['share']!r}",
                  f"      income_decile_range: {a['income_decile_range']}",
                  f"      tenure_mix:   {fmt(a['tenure_mix'])}",
                  f"      building_mix: {fmt(a['building_mix'])}"]
    return "\n".join(lines)


if __name__ == "__main__":
    print(as_yaml(derive_archetypes()))
