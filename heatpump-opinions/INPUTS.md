# Simulation Inputs

All inputs live in [`settings.yaml`](settings.yaml). Defaults shown below.
The dynamics values are placeholders, calibrated only to year-1 installs of
roughly 0.3% of homes a year (see
[`analysis/negative_wom/RESULTS.md`](analysis/negative_wom/RESULTS.md), table 5).

## simulation

| Parameter | Default | Meaning |
|---|---|---|
| `months` | 300 | Months to simulate (one step is one month; 300 = 25 years) |
| `random_seed` | 42 | Seed for all randomness in a run (network, starting state, dynamics) |

## households

| Parameter | Default | Meaning |
|---|---|---|
| `location_source` | file | `file` loads a world file (stage one output); `generate` synthesises households in-process |
| `households_source_file` | worlds/model_town.csv | World file path when `location_source: file` — see [WORLD_FORMAT.md](WORLD_FORMAT.md). The file is authoritative on population size |
| `n_households` | 100 | Households to synthesise (`generate` mode only) |
| `space_size` | [1.0, 1.0] | Width/height of the space (`generate` mode only) |
| `characteristic_field.n_centers` | 8 | Number of random spatial "hotspots" summed to build the characteristic (`generate` mode only) |
| `characteristic_field.length_scale` | 0.3 | How quickly a hotspot's influence decays with distance |
| `characteristic_field.noise_std` | 0.15 | Random noise added on top of the smooth spatial field |

`generate` mode produces no descriptive attributes, so it cannot be used with
`word_of_mouth.similar_home_credibility` (which needs building types) and
reports no results by LSOA type.

## adoption

| Parameter | Default | Meaning |
|---|---|---|
| `initial_fraction` | 0.01 | Share of households owning a heat pump at month 0 (~1% today) |
| `initial_owners` | top | `top`: first owners drawn from the top `top_pool_fraction` by `characteristic`; `random`: from everyone |
| `top_pool_fraction` | 0.10 | Size of that top slice |
| `trigger_rate` | 1/180 | Chance a month that a non-owner reconsiders its heating (boiler replacement, moving, renovation): a ~15-year boiler life |
| `capability_gate` | 0.30 | Households with `characteristic` below this can never adopt |
| `half_point` | 0.8 | Motivation at which a triggered household adopts with probability 1/2 ... |
| `characteristic_weight` | 0.2 | ... lowered by `characteristic_weight × characteristic`, so better-placed households need less motivation |
| `slope` | 0.07 | How sharply the adoption probability rises with motivation (logistic scale) |

## motivation

| Parameter | Default | Meaning |
|---|---|---|
| `baseline_mean` | 0.3 | Mean of households' own baseline motivation (0-1), calibrated |
| `baseline_sd` | 0.15 | Spread of baseline motivation |
| `memory` | 0.05 | Share of the gap back to baseline closed each month: what people hear fades |

## word_of_mouth

Only owners talk.

| Parameter | Default | Meaning |
|---|---|---|
| `contact_rate` | 0.72 | Chance a month that an owner talks to each of its contacts (DESIGN.md) |
| `message_strength` | 0.06 | Share of the gap to 1 that a satisfied owner's message closes, calibrated |
| `complex_contagion_beta` | 1.0 | Option A. Above 1, several voices in a month count for more than one: effective messages = messages × (messages / reference)^(beta − 1). 1 is off |
| `complex_contagion_reference` | 2 | The number of voices at which option A neither boosts nor discounts |
| `similar_home_credibility` | 0.0 | Option B. A message from an owner in a different building type counts (1 − this). 0 is off |

Turning on option A or B slows adoption at a given `message_strength`; to
compare options at the same pace, recalibrate `message_strength` (Michael's
values are in RESULTS.md, table 6).

## dissatisfaction

The negative word-of-mouth lever.

| Parameter | Default | Meaning |
|---|---|---|
| `share` | 0.0 | Chance a new owner (including first owners) is dissatisfied (q) |
| `weight` | 1.0 | A complaint pushes motivation down as hard as this many positive messages push it up (w); 0 makes dissatisfied owners silent |
| `duration_months` | null | Mean months a dissatisfied owner keeps complaining before falling silent; `null` = forever. Silent dissatisfied owners still do not speak positively |

## world_generation

Stage one only (`generate_world.py`); the simulation never reads this section.

| Parameter | Default | Meaning |
|---|---|---|
| `seed` | 7 | Seed for world generation (separate from `simulation.random_seed`) |
| `n_households` | 400 | Households to generate, used only when `households_per_cell` is null |
| `households_per_cell` | 694 | Households per cell, the mean for an English LSOA; 11,104 on the 4×4 grid |
| `space_size` | [1.0, 1.0] | Extent of the model town |
| `grid` | [4, 4] | Rows, cols of LSOA-like cells tiling the town |
| `mixing` | 0.3 | `0` = clean affluence gradient across the grid, `1` = archetypes scattered at random. The segregation knob |
| `output_file` | worlds/model_town.csv | Where to write the world file |
| `capability.weights` | income 0.5, tenure 0.3, building 0.2 | Relative contribution of each attribute to `characteristic` (normalised internally) |
| `capability.noise_std` | 0.05 | Household-level variation within an archetype |
| `capability.tenure_scores` | see settings | Capability score per tenure — **placeholder, revisit** |
| `capability.building_scores` | see settings | Capability score per building type — **placeholder, revisit** |
| `archetypes` | six LSOA types | Per-type `share`, `income_decile_range`, `tenure_mix`, `building_mix`, from `analysis/derive_archetypes.py`. Order is irrelevant; sorted by mean income decile when laid out |

## network

| Parameter | Default | Meaning |
|---|---|---|
| `type` | spatial_kernel | `spatial_kernel`; or `preferential_attachment`, `random`, `small_world` as comparators |
| `params.mean_degree` | 15 | Average ties per household (`spatial_kernel`) |
| `params.decay_length_m` | 210 | Distance over which the chance of a local tie falls by a factor of e |
| `params.long_range_fraction` | 0.30 | Share of ties placed ignoring geography |
| `params.metres_per_unit` | 2000 | Metres per unit of world coordinates — **placeholder** (2 km town, 500 m cells) |
| `params.m`, `params.p`, `params.k` | — | Parameters of the comparator networks |
| `rewire` | false | Shuffle who is tied to whom, keeping each household's number of ties: a null for whether structure matters |

## output

| Parameter | Default | Meaning |
|---|---|---|
| `results_dir` | results | Output directory |
| `animation` | adoption_animation.gif | Motivation and ownership animation filename |
| `animation_every_months` | 3 | One animation frame per this many months |
| `fps` | 8 | Animation frame rate |
