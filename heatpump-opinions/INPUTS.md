# Simulation Inputs

All inputs live in [`settings.yaml`](settings.yaml). Defaults shown below.

## simulation

| Parameter | Default | Meaning |
|---|---|---|
| `num_timesteps` | 100 | Number of turns to simulate |
| `random_seed` | 42 | Seed for all randomness (reproducibility) |

## households

| Parameter | Default | Meaning |
|---|---|---|
| `n_households` | 100 | Number of agents |
| `space_size` | [1.0, 1.0] | Width/height of the geographic space |
| `location_source` | file | `file` loads a world file (stage one output); `generate` synthesises households in-process |
| `households_source_file` | worlds/model_town.csv | World file path when `location_source: file` — see [WORLD_FORMAT.md](WORLD_FORMAT.md). The file is authoritative on population size |
| `characteristic_field.n_centers` | 8 | Number of random spatial "hotspots" summed to build the demographic field |
| `characteristic_field.length_scale` | 0.3 | How quickly a hotspot's influence decays with distance |
| `characteristic_field.noise_std` | 0.15 | Random noise added on top of the smooth spatial field |

The `characteristic` is a single demographic/economic number in [0, 1] per household, spatially correlated so nearby households tend to be similar. The `characteristic_field.*` settings apply only in `generate` mode; in `file` mode the number comes from the world file.

## world_generation

Stage one only (`generate_world.py`); the simulation never reads this section.

| Parameter | Default | Meaning |
|---|---|---|
| `seed` | 7 | Seed for world generation (separate from `simulation.random_seed`) |
| `n_households` | 400 | Households to generate |
| `space_size` | [1.0, 1.0] | Extent of the model town |
| `grid` | [4, 4] | Rows, cols of LSOA-like cells tiling the town |
| `mixing` | 0.3 | `0` = clean affluence gradient across the grid, `1` = archetypes scattered at random. The segregation knob |
| `output_file` | worlds/model_town.csv | Where to write the world file |
| `capability.weights` | income 0.5, tenure 0.3, building 0.2 | Relative contribution of each attribute to `characteristic` (normalised internally) |
| `capability.noise_std` | 0.05 | Household-level variation within an archetype |
| `capability.tenure_scores` | see settings | Capability score per tenure — **placeholder, revisit** |
| `capability.building_scores` | see settings | Capability score per building type — **placeholder, revisit** |
| `archetypes` | 3 archetypes | Per-archetype `share`, `income_decile_range`, `tenure_mix`, `building_mix` — **placeholders** standing in for real LSOA data. Order is irrelevant; sorted by mean income decile when laid out |

## heatpumps

| Parameter | Default | Meaning |
|---|---|---|
| `initial_fraction` | 0.05 | Fraction of households starting with a heat pump |
| `top_pool_fraction` | 0.10 | Initial owners are drawn from this top slice by `characteristic` |
| `install_threshold` | 0.95 | Base opinion level that triggers a new install |
| `characteristic_weight` | 0.2 | Discounts a household's own install threshold by `characteristic_weight * characteristic` — higher-characteristic households need less opinion to adopt (set to 0 to disable) |
| `characteristic_gate` | 0.15 | Households with `characteristic` below this can never adopt, regardless of opinion — a hard structural barrier, distinct from the graded discount above (set to 0 to disable) |
| `breakdown_rate` | 0.01 | Per-turn probability a working heat pump breaks down |

## opinions

| Parameter | Default | Meaning |
|---|---|---|
| `initial_mean` | 0.5 | Mean of each household's starting opinion (0-1) |
| `initial_std` | 0.15 | Std. dev. of starting opinion |
| `self_increase_rate` | 0.10 | Per-turn opinion increase for happy (non-broken) owners |
| `social_influence_rate` | 0.12 | Weight given to the mean opinion of network neighbours |
| `noise_std` | 0.10 | Random perturbation applied to opinion each turn — drives the stochastic tipping needed for adoption to spread (see [README](README.md)) |

## network

| Parameter | Default | Meaning |
|---|---|---|
| `type` | preferential_attachment | Social network topology: `preferential_attachment`, `random`, or `small_world` |
| `params.m` | 3 | Edges each new node attaches with (Barabási–Albert, used by `preferential_attachment`) |
| `params.p` | — | Edge probability (`random`) or rewiring probability (`small_world`) |
| `params.k` | — | Each node's initial neighbours (`small_world`) |

## output

| Parameter | Default | Meaning |
|---|---|---|
| `results_dir` | results | Output directory |
| `opinion_animation` | opinion_animation.gif | Opinion-only animation filename |
| `heatpump_animation` | heatpump_animation.gif | Adoption-only animation filename |
| `combined_animation` | combined_animation.gif | Side-by-side animation filename |
| `fps` | 8 | Animation frame rate |
