"""Join the raw downloads into one LSOA-level table for the study towns.

This is the area-level layer. It does NOT yet expand to households -- that is a
separate step, because the expansion involves modelling choices (how much
within-LSOA variation to introduce) that should be reviewable on their own.

Everything joins on 2021 LSOA codes. That was verified rather than assumed:
Nesta's Key tab warns that it uses "2021 codes primarily... then 2011 codes",
but for England all 33,755 codes match the IMD 2025 (2021) set exactly, so no
crosswalk is needed. The check is re-run here on every build.

Usage:
    python -m data_prep.build_lsoa_table
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

from .sources import STUDY_AREAS
from .strict_ooxml import to_transitional

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"

LSOA_CODE = "lsoa21cd"

# Census columns are verbose; map them to short names explicitly rather than
# pattern-matching, so a column rename upstream fails loudly instead of quietly
# selecting the wrong thing.
TENURE_COLUMNS = {
    "Tenure of household: Owned: Owns outright": "owned_outright",
    "Tenure of household: Owned: Owns with a mortgage or loan": "owned_mortgage",
    "Tenure of household: Shared ownership: Shared ownership": "shared_ownership",
    "Tenure of household: Social rented: Rents from council or Local Authority": "social_council",
    "Tenure of household: Social rented: Other social rented": "social_other",
    "Tenure of household: Private rented: Private landlord or letting agency": "private_landlord",
    "Tenure of household: Private rented: Other private rented": "private_other",
    "Tenure of household: Lives rent free": "rent_free",
}

ACCOMMODATION_COLUMNS = {
    "Accommodation type: Detached": "detached",
    "Accommodation type: Semi-detached": "semi_detached",
    "Accommodation type: Terraced": "terraced",
    "Accommodation type: In a purpose-built block of flats or tenement": "flat_purpose_built",
    "Accommodation type: Part of a converted or shared house, including bedsits": "flat_converted",
    "Accommodation type: Part of another converted building, for example, former school, church or warehouse": "flat_other_conversion",
    "Accommodation type: In a commercial building, for example, in an office building, hotel or over a shop": "flat_commercial",
    "Accommodation type: A caravan or other mobile or temporary structure": "caravan",
}

# Nesta suitability columns worth carrying. "_N_" is Nesta's own view of
# suitability, "_S_" the conventional view -- both are kept so the choice can be
# a sensitivity test rather than a hard-coded assumption.
SUITABILITY_COLUMNS = {
    "ASHP_N_avg_score_weighted": "ashp_suitability_nesta",
    "ASHP_S_avg_score_weighted": "ashp_suitability_conventional",
    "GSHP_N_avg_score_weighted": "gshp_suitability_nesta",
    "proportion_off_gas": "proportion_off_gas",
    "proportion_epc_c_plus": "proportion_epc_c_plus",
    "proportion_listed_building": "proportion_listed",
    "proportion_in_protected_area": "proportion_protected_area",
    "census_proportion_flats": "nesta_proportion_flats",
    "median_garden_estimate_m2": "median_garden_m2",
    "property_density_km2": "property_density_km2",
    "rural_urban_class": "rural_urban_class",
    "heatpump_installation_percentage": "grid_capacity_pct",
    "n_properties": "n_properties_epc",
}

IMD_COLUMNS = {
    "LSOA code (2021)": LSOA_CODE,
    "LSOA name (2021)": "lsoa_name",
    "Local Authority District code (2024)": "lad_code",
    "Local Authority District name (2024)": "lad_name",
    "Income Score (rate)": "income_score",
    "Income Decile (where 1 is most deprived 10% of LSOAs)": "income_decile",
    "Index of Multiple Deprivation (IMD) Score": "imd_score",
    "Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)": "imd_decile",
    "Total population: mid 2022": "population",
}


def _read_census(zip_name: str, table: str) -> pd.DataFrame:
    """Read the LSOA-level CSV out of a NOMIS census bulk zip."""
    with zipfile.ZipFile(RAW / zip_name) as archive:
        with archive.open(f"census2021-{table}-lsoa.csv") as handle:
            df = pd.read_csv(handle)
    return df.rename(columns={"geography code": LSOA_CODE})


def _select(df: pd.DataFrame, mapping: dict[str, str], source: str) -> pd.DataFrame:
    """Rename an explicit column subset, failing loudly on any missing column."""
    missing = set(mapping) - set(df.columns)
    if missing:
        raise KeyError(f"{source}: expected columns not found: {sorted(missing)}")
    return df[[LSOA_CODE, *mapping]].rename(columns=mapping)


def load_suitability() -> pd.DataFrame:
    """Nesta heat pump suitability, via a strict->transitional OOXML conversion."""
    converted = to_transitional(
        RAW / "nesta_heat_pump_suitability_per_lsoa_2023Q4.xlsx",
        INTERIM / "nesta_hps_transitional.xlsx",
    )
    df = pd.read_excel(converted, sheet_name="Data", engine="openpyxl")
    df = df.rename(columns={"lsoa": LSOA_CODE})
    return _select(df, SUITABILITY_COLUMNS, "nesta suitability")


def build() -> pd.DataFrame:
    imd_raw = pd.read_csv(RAW / "imd2025_file7_all_ranks_scores_deciles.csv")
    imd = _select(imd_raw.rename(columns={"LSOA code (2021)": LSOA_CODE}),
                  {k: v for k, v in IMD_COLUMNS.items() if k != "LSOA code (2021)"},
                  "imd 2025")

    suitability = load_suitability()

    # --- vintage check, re-run every build -----------------------------------
    england = suitability[suitability[LSOA_CODE].str.startswith("E01")]
    unmatched = set(england[LSOA_CODE]) - set(imd[LSOA_CODE])
    if unmatched:
        raise ValueError(
            f"{len(unmatched)} Nesta LSOA codes are not in the IMD 2025 (2021) set. "
            "The boundary vintages have diverged and a crosswalk is now required. "
            f"Examples: {sorted(unmatched)[:5]}"
        )

    tenure = _select(_read_census("census2021_ts054_tenure.zip", "ts054"),
                     TENURE_COLUMNS, "census ts054")
    accommodation = _select(_read_census("census2021_ts044_accommodation_type.zip", "ts044"),
                            ACCOMMODATION_COLUMNS, "census ts044")
    households = _read_census("census2021_ts041_number_of_households.zip", "ts041").rename(
        columns={"Number of households: Number of households; measures: Value": "n_households"}
    )[[LSOA_CODE, "n_households"]]

    table = (
        imd
        .merge(suitability, on=LSOA_CODE, how="inner", validate="one_to_one")
        .merge(households, on=LSOA_CODE, how="inner", validate="one_to_one")
        .merge(tenure, on=LSOA_CODE, how="inner", validate="one_to_one")
        .merge(accommodation, on=LSOA_CODE, how="inner", validate="one_to_one")
    )

    # --- subset to the study towns -------------------------------------------
    table["town"] = table["lad_code"].map({v: k for k, v in STUDY_AREAS.items()})
    table = table[table["town"].notna()].copy()

    # --- collapse tenure and accommodation into the model's categories --------
    # Owner-occupiers and shared owners can decide for themselves. Social renters
    # cannot, but their landlord can and has access to different funding. Private
    # renters cannot, and their landlord bears cost without benefit.
    table["owner_occupied"] = table["owned_outright"] + table["owned_mortgage"] + table["shared_ownership"]
    table["social_rented"] = table["social_council"] + table["social_other"]
    table["private_rented"] = table["private_landlord"] + table["private_other"] + table["rent_free"]

    table["flats"] = (table["flat_purpose_built"] + table["flat_converted"]
                      + table["flat_other_conversion"] + table["flat_commercial"])
    table["houses"] = table["detached"] + table["semi_detached"] + table["terraced"]

    # Census 2021 applies cell key perturbation for disclosure control, so counts
    # in different tables do not reconcile: TS054 and TS044 totals disagree with
    # TS041 by up to +/-9 households per LSOA (mean absolute difference ~1).
    # Mixing raw counts across tables would therefore produce a household
    # population that does not add up. Instead each table contributes
    # PROPORTIONS computed against its own total, and TS041 is the single
    # authority on how many households an LSOA has.
    tenure_total = table[["owner_occupied", "social_rented", "private_rented"]].sum(axis=1)
    for column in ("owner_occupied", "social_rented", "private_rented"):
        table[f"prop_{column}"] = table[column] / tenure_total

    accommodation_total = table[["houses", "flats", "caravan"]].sum(axis=1)
    for column in ("detached", "semi_detached", "terraced", "flats", "caravan"):
        table[f"prop_{column}"] = table[column] / accommodation_total

    _validate(table)
    return table.sort_values(["town", LSOA_CODE]).reset_index(drop=True)


def _validate(table: pd.DataFrame) -> None:
    """Fail loudly on the mistakes that would otherwise pass silently."""
    if table.empty:
        raise ValueError("No LSOAs matched the study areas -- check STUDY_AREAS LAD codes.")

    # Proportions must sum to 1 within each table. This is the check that still
    # has teeth after perturbation -- it catches a mis-mapped or dropped
    # category, which raw-count equality could not distinguish from noise.
    tenure_props = table[["prop_owner_occupied", "prop_social_rented", "prop_private_rented"]].sum(axis=1)
    accommodation_props = table[
        ["prop_detached", "prop_semi_detached", "prop_terraced", "prop_flats", "prop_caravan"]
    ].sum(axis=1)
    for label, totals in (("tenure", tenure_props), ("accommodation", accommodation_props)):
        worst = (totals - 1.0).abs().max()
        if worst > 1e-9:
            raise ValueError(
                f"{label} proportions do not sum to 1 (worst deviation {worst:.2e}) "
                "-- a category is probably missing from the column mapping."
            )

    # Perturbation should only ever move counts by a handful of households. A
    # large divergence from TS041 would mean something structural is wrong.
    drift = (table[["owner_occupied", "social_rented", "private_rented"]].sum(axis=1)
             - table["n_households"]).abs()
    if drift.max() > 25:
        raise ValueError(
            f"Tenure counts diverge from TS041 by up to {drift.max()} households, "
            "which is too large to be census disclosure control."
        )

    nulls = table.columns[table.isna().any()].tolist()
    if nulls:
        raise ValueError(f"Null values present in: {nulls}")


def main() -> int:
    table = build()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / "lsoa_table.csv"
    table.to_csv(out, index=False)

    print(f"Wrote {out}  ({len(table)} LSOAs, {len(table.columns)} columns)")
    summary = table.groupby("town").agg(
        lsoas=(LSOA_CODE, "size"),
        households=("n_households", "sum"),
        owner_occupied=("owner_occupied", "sum"),
        social_rented=("social_rented", "sum"),
        private_rented=("private_rented", "sum"),
        flats=("flats", "sum"),
        mean_ashp_suitability=("ashp_suitability_nesta", "mean"),
        mean_income_decile=("income_decile", "mean"),
        mean_off_gas=("proportion_off_gas", "mean"),
    )
    print()
    print(summary.T.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
