"""Data collection and preparation: the national LSOA table.

Downloads Census 2021, IMD 2025 and Nesta data and joins them into one table
of England's LSOAs (`data/processed/lsoa_table.csv`). That table feeds the
LSOA typology (`analysis/lsoa_types.py`), from which
`analysis/derive_archetypes.py` builds the archetypes in settings.yaml.

Kept separate from `heatpump_sim` so the simulation itself has no dependency on
the data pipeline: the simulation reads only settings.yaml and world files.
"""
