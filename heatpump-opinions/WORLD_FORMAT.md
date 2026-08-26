# World file format

A **world file** describes the synthetic population a simulation runs on:
where each household sits and what it is like. It is the only thing passed
between the two stages of the model.

```
generate_world.py  ──▶  worlds/model_town.csv  ──▶  run_simulation.py
   (stage one)              (this format)              (stage two)
```

Keeping the stages apart means the assumptions about *who lives where* can
be changed, swapped for real data, or varied in a sweep without touching
the adoption dynamics — and a run can always be traced back to the exact
population it used.

Implemented by `heatpump_sim/world.py`. Worked examples, including a small
one you can read end to end, are in
[`examples/worlds/`](examples/worlds/README.md).

## Shape

CSV, one row per household, preceded by a block of `#` comment lines
carrying provenance metadata. Readers skip the comment block.

```
# heatpump-opinions world file, format version 1
# households: 400
# generated: 2026-08-26T12:17:44+00:00
# seed: 7
# grid: 4x4
# mixing: 0.3
# space_size: 1.0x1.0
# archetypes: deprived_urban, mixed_suburban, affluent_periphery
id,x,y,characteristic,lsoa_id,lsoa_archetype,income_decile,tenure,building_type
0,0.248875,0.220083,0.341503,C000,deprived_urban,1,social_rented,semi_detached
1,0.198165,0.127448,0.178077,C000,deprived_urban,2,social_rented,flat
```

## Core columns — required

The simulation refuses to load a file without all four.

| Column | Type | Meaning |
|---|---|---|
| `id` | integer | Unique household identifier |
| `x`, `y` | float | Position in the geographic space |
| `characteristic` | float in [0, 1] | The demographic/economic capability number |

`characteristic` is stored rather than recomputed at load time. How it is
composed is a world-generation question; the simulation only needs the
number. That is what keeps the two stages independent.

## Descriptive columns — optional

Carried through to the results untouched and available for analysis. The
core dynamics never read them: they exist so a run can be broken down after
the fact, and so the provenance of `characteristic` is not lost.

| Column | Values |
|---|---|
| `lsoa_id` | Identifier of the LSOA-like cell |
| `lsoa_archetype` | Name of the archetype that cell was drawn from |
| `income_decile` | 1–10 |
| `tenure` | `owner_occupied`, `private_rented`, `social_rented` |
| `building_type` | `detached`, `semi_detached`, `terraced`, `flat` |

Any **further** columns are preserved as descriptive attributes too, so the
format can carry real survey fields later with no code change.

In the results, these arrive in `results/history.npz` under an `attr_`
prefix — `attr_tenure`, `attr_building_type`, and so on:

```python
d = np.load("results/history.npz")
adopted_by_tenure = {
    t: d["heatpump_history"][-1][d["attr_tenure"] == t].mean()
    for t in np.unique(d["attr_tenure"])
}
```

## Validation

A silently misread population produces plausible-looking but meaningless
results, so the reader is strict and reports the offending line:

- missing required column → lists what was required and what was found
- unparseable or empty value → `path:line: could not read 'y' value 'oops' as float`
- `characteristic` outside [0, 1] → rejected
- duplicate `id`s → rejected
- non-finite coordinates → rejected

## Supplying your own world

Any CSV with the four core columns will load — the generator is a
convenience, not a requirement. Point the simulation at it:

```yaml
households:
  location_source: file
  households_source_file: worlds/my_world.csv
```

The file is authoritative on population size; `households.n_households` is
only consulted when `location_source: generate`.
