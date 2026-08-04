"""Manifest of external datasets used to build the household population.

Single source of truth for where every input came from. Each entry records the
licence and the geography/vintage, because the joins downstream are only valid
if the LSOA boundary years line up (see `lsoa_vintage`).

Note on `heat_pump_suitability`: Nesta are retiring the heat pump suitability
map and folding the work into a local clean heat planning tool, so this URL is
expected to disappear. The downloaded file is a pinned snapshot -- do not
re-point this at a "latest" endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    key: str
    filename: str
    url: str
    description: str
    licence: str
    lsoa_vintage: str   # boundary year the data is published on; "n/a" if not LSOA-based
    source_page: str    # human-facing landing page, for citation


SOURCES: tuple[Source, ...] = (
    Source(
        key="heat_pump_suitability",
        filename="nesta_heat_pump_suitability_per_lsoa_2023Q4.xlsx",
        url=(
            "https://nesta-open-data.s3.eu-west-2.amazonaws.com/"
            "asf_heat_pump_suitability/2023Q4/"
            "20250319_2023_Q4_EPC_heat_pump_suitability_per_lsoa.xlsx"
        ),
        description=(
            "Nesta heat pump suitability scores per LSOA, Great Britain, built "
            "from 2023 Q4 EPC data. Feeds the model's `capability` field."
        ),
        licence="CC BY-NC-SA 4.0 (non-commercial, share-alike) -- check before redistributing",
        # The workbook's Key tab warns "2021 codes primarily used for England and
        # Wales, then 2011 codes". Verified on download: for England all 33,755
        # E01 codes match the IMD 2025 (2021) set exactly, so no crosswalk is
        # needed here. The mixed vintage presumably affects Wales/Scotland.
        # build_lsoa_table re-runs this check on every build.
        lsoa_vintage="2021 (verified: 33,755/33,755 England codes match IMD 2025)",
        source_page="https://www.nesta.org.uk/project/mapping-heat-pump-suitability-across-great-britain/",
    ),
    Source(
        key="imd_2025",
        filename="imd2025_file7_all_ranks_scores_deciles.csv",
        url=(
            "https://assets.publishing.service.gov.uk/media/"
            "691ded56d140bbbaa59a2a7d/"
            "File_7_IoD2025_All_Ranks_Scores_Deciles_Population_Denominators.csv"
        ),
        description=(
            "English Indices of Deprivation 2025, all ranks/scores/deciles per "
            "LSOA plus population denominators. The Income Deprivation domain is "
            "the affordability proxy; it is built FROM means-tested benefit and "
            "tax credit receipt, so do not also add a separate benefits-receipt "
            "variable -- that double-counts. Also carries the LSOA -> local "
            "authority lookup used to subset to the study towns."
        ),
        licence="Open Government Licence v3.0",
        lsoa_vintage="2021",
        source_page="https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025",
    ),
    Source(
        key="census_tenure",
        filename="census2021_ts054_tenure.zip",
        url="https://www.nomisweb.co.uk/output/census/2021/census2021-ts054.zip",
        description=(
            "Census 2021 TS054 Tenure, counts per LSOA. Drives the per-household "
            "tenure draw, which decides who is even a decision-maker and which "
            "funding route applies."
        ),
        licence="Open Government Licence v3.0",
        lsoa_vintage="2021",
        source_page="https://www.nomisweb.co.uk/sources/census_2021_bulk",
    ),
    Source(
        key="census_accommodation",
        filename="census2021_ts044_accommodation_type.zip",
        url="https://www.nomisweb.co.uk/output/census/2021/census2021-ts044.zip",
        description=(
            "Census 2021 TS044 Accommodation type, counts per LSOA. Used to give "
            "each household a dwelling type so capability varies WITHIN an LSOA "
            "rather than every neighbour sharing one area-mean suitability score."
        ),
        licence="Open Government Licence v3.0",
        lsoa_vintage="2021",
        source_page="https://www.nomisweb.co.uk/sources/census_2021_bulk",
    ),
    Source(
        key="census_households",
        filename="census2021_ts041_number_of_households.zip",
        url="https://www.nomisweb.co.uk/output/census/2021/census2021-ts041.zip",
        description=(
            "Census 2021 TS041 Number of households per LSOA. Sets how many agents "
            "to generate in each LSOA."
        ),
        licence="Open Government Licence v3.0",
        lsoa_vintage="2021",
        source_page="https://www.nomisweb.co.uk/sources/census_2021_bulk",
    ),
)

SOURCES_BY_KEY = {s.key: s for s in SOURCES}

# Local authority districts for the study towns. Confirmed against the IMD 2025
# LSOA -> local authority lookup at download time.
STUDY_AREAS = {
    "Nottingham": "E06000018",
    "Derby": "E06000015",
}
