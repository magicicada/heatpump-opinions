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
| `location_source` | generate | `generate` synthetic households, or `file` to load them |
| `households_source_file` | null | CSV path (columns: `id,x,y,characteristic`) when `location_source: file` |
| `characteristic_field.n_centers` | 8 | Number of random spatial "hotspots" summed to build the demographic field |
| `characteristic_field.length_scale` | 0.3 | How quickly a hotspot's influence decays with distance |
| `characteristic_field.noise_std` | 0.15 | Random noise added on top of the smooth spatial field |

The `characteristic` is a single demographic/economic number in [0, 1] per household, spatially correlated so nearby households tend to be similar.

## heatpumps

| Parameter | Default | Meaning |
|---|---|---|
| `initial_fraction` | 0.05 | Fraction of households starting with a heat pump |
| `top_pool_fraction` | 0.10 | Initial owners are drawn from this top slice by `characteristic` |
| `install_threshold` | 0.95 | Opinion level that triggers a new install |
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
