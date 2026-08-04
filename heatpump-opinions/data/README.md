# Data

Inputs for the real-geography version of the model, covering **Nottingham
(E06000018)** and **Derby (E06000015)**.

```
data/
  raw/         downloaded snapshots -- gitignored, recreate with the downloader
    MANIFEST.md  committed: URL, licence, retrieval date and SHA256 of each file
  interim/     format conversions (gitignored)
  processed/   lsoa_table.csv -- the joined area-level table (gitignored)
```

## Rebuilding

```
python -m data_prep.download          # fetch raw snapshots (~25 MB)
python -m data_prep.build_lsoa_table  # join -> data/processed/lsoa_table.csv
```

Both steps are idempotent. Raw files are not committed: they are large, and the
Nesta dataset is CC BY-NC-SA, so redistributing it inside this repo would impose
that licence on anything downstream. `MANIFEST.md` records the hashes, which is
what makes a past result reproducible after the upstream files move.

## Two things that will bite you

**The Nesta workbook is Strict OOXML.** openpyxl reports it as having *zero
sheets* and raises nothing at all, so `pd.read_excel` returns nothing and a
careless pipeline silently produces an empty table. python-calamine fails
differently (`Relationship not found`). `data_prep/strict_ooxml.py` rewrites the
namespaces to Transitional before reading. Do not remove that step.

**Census tables do not reconcile with each other.** Census 2021 applies cell key
perturbation for disclosure control, so TS054 (tenure) and TS044 (accommodation)
totals disagree with TS041 (household counts) by up to +/-9 households per LSOA,
mean absolute difference ~1. Mixing raw counts across tables produces a
population that does not add up. The build therefore takes **proportions** from
each table against its own total, and treats TS041 as the sole authority on how
many households an LSOA contains.

## Boundary vintages

Everything is on **2021 LSOA boundaries** and joins exactly -- 33,755 of 33,755
English LSOAs match across Nesta, IMD 2025 and Census 2021, and coverage of both
study towns is 100%. This was verified, not assumed: Nesta's Key tab warns it
uses "2021 codes primarily... then 2011 codes", but that mixed vintage evidently
applies to Wales and Scotland. `build_lsoa_table` re-runs the check on every
build and refuses to produce a table if the vintages ever diverge.

## Attribution

The Nesta dataset requires onward attribution of its own sources: OS data (c)
Crown copyright and database right 2025; Royal Mail data (c) Royal Mail
copyright and database right 2025; ONS information and other public sector
information licensed under the Open Government Licence v3.0. IMD 2025 and the
Census tables are OGL v3.0.

Nesta are retiring the heat pump suitability map in favour of a local clean heat
planning tool, so the download URL is expected to break. The snapshot in
`MANIFEST.md` is the version this work is built on.

## Not yet collected

- **Motivation baseline.** The DESNZ Public Attitudes Tracker is published as
  reports rather than microdata and has no small-area breakdown, so it cannot be
  spatially disaggregated to LSOA. It can supply a national distribution
  conditioned on tenure -- a modelling decision that has not been made yet.
- **Household coordinates.** Needed to place agents and to build a
  spatially-embedded network. Options are the ONS Postcode Directory (best
  clustering, ~1 GB) or LSOA population-weighted centroids (small, cruder).
- **MCS installation records.** Wanted for seeding initial adopters and for
  validation. Not openly published at postcode level.
- **ONS small-area income.** Only available at MSOA, and partially redundant
  with the IMD Income domain -- see the note in `data_prep/sources.py` about
  double-counting benefits receipt.
