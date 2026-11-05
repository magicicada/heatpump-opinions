# Heat Pump Adoption Simulation

Agent-based simulation of heat pump adoption over a social network of
households, driven by owners' word of mouth — good and bad — and by the
moments when a household reconsiders its heating.

## Run it

The model runs in two stages. Stage one builds a synthetic population and
writes it to a **world file**; stage two simulates adoption on it.

```bash
python3 generate_world.py --settings settings.yaml   # -> worlds/model_town.csv
python3 run_simulation.py --settings settings.yaml   # -> results/
```

Each run writes to its own subdirectory of `results/`, named after the world
it ran on, so runs sit side by side instead of overwriting each other:

```
results/segregated_town/
    history.npz         monthly arrays (ownership, dissatisfaction, motivation) and world attributes
    network.graphml     the social network
    run_info.json       what produced this run — world, seed, parameters, outcome
    *.gif               animation of motivation and ownership
```

Useful flags: `--world <path>` and `--seed <n>` to override the settings for
one run, `--run-name` to name the output directory, and `--no-animations`
to skip GIF rendering (which takes a few minutes on an LSOA-scale world).

```bash
python3 run_simulation.py --world examples/worlds/mixed_town.csv --no-animations
```

## Comparing worlds

`analysis/world_comparison_sweep.py` runs two or more worlds across many
simulation seeds and reports a paired comparison:

```bash
python3 analysis/world_comparison_sweep.py --seeds 30
```

It defaults to the `segregated_town` / `mixed_town` pair in
[`examples/worlds/`](examples/worlds/README.md), which differ only in how
segregated the town is. Both hold the same number of households at the same
coordinates, so a given seed produces the same starting motivations and — even
with the spatial network — the same social network in both. The pairing is
tight and the only difference is who lives where.
Writes a per-run CSV and a summary figure to `analysis/`.

The two stages are deliberately separate: assumptions about *who lives
where* can be changed, swapped for real data, or swept without touching the
adoption dynamics, and every run can be traced back to the exact population
it used. The world file is the only contract between them — see
[WORLD_FORMAT.md](WORLD_FORMAT.md). To skip stage one and generate
households in-process instead, set `households.location_source: generate`.

## Structure

- `settings.yaml` — every tunable parameter for both stages (world
  generation, network, adoption, motivation, word of mouth,
  dissatisfaction, output paths).
- `generate_world.py` / `heatpump_sim/worldgen.py` — **stage one**. Tiles a
  model town with a grid of LSOA-like cells, assigns each an archetype
  (distributions over tenure, building type and income decile), draws
  households inside it and composes their `characteristic` from the drawn
  attributes. The archetypes are the six LSOA types from
  `analysis/lsoa_types.py`, derived by `analysis/derive_archetypes.py`. Cells hold `world_generation.households_per_cell` households
  (694 by default, the mean for an English LSOA), so the default world has
  11,104 households; the small committed examples are for reading and
  quick tests, not results — see
  [`examples/worlds/`](examples/worlds/README.md). The `world_generation.mixing` knob runs from a clean
  affluence gradient across the town (`0`) to archetypes scattered at
  random (`1`) — the "how segregated is this town" axis.
- `heatpump_sim/world.py` — the world file format: schema, reader, writer,
  validation. See [WORLD_FORMAT.md](WORLD_FORMAT.md).
- `heatpump_sim/agents.py` — loads a world file, or (in `generate` mode)
  synthesises locations and a spatially-correlated `characteristic`
  directly, then sets baseline motivations, the first owners and which of
  them start dissatisfied.
- `heatpump_sim/network.py` — builds the social network, selected via
  `network.type`. The default, `spatial_kernel`, follows the network
  review in the 26 Aug briefing: a local tie between two households forms
  with probability proportional to `exp(-distance / decay_length_m)`,
  scaled so households average `mean_degree` ties, and a further
  `long_range_fraction` of ties are placed ignoring geography. Each edge is
  tagged `kind: local` or `kind: long`. World coordinates are converted to
  metres with `metres_per_unit`, currently a placeholder (2 km town, 500 m
  cells). A warning is raised if the world is too sparse for the requested
  degree, in which case the realised decay is flatter than asked for.
  `preferential_attachment` (Barabási–Albert), `random` (Erdős–Rényi) and
  `small_world` (Watts–Strogatz) remain available; BA is kept only as an
  unrealistic comparator. `network.rewire: true` shuffles who is tied to
  whom while keeping everyone's number of ties, as a null for "does the
  network's structure matter?". Each run's `run_info.json` records a
  `network_summary`, including the realised and expected share of ties that
  cross a cell boundary.
- `heatpump_sim/dynamics.py` — the monthly update (see its docstring for
  the equations):
  1. **Word of mouth from experience.** Only owners talk, each to each
     contact with probability `contact_rate` a month. A satisfied owner's
     message raises the listener's motivation; a dissatisfied owner's
     complaint lowers it, counting as `dissatisfaction.weight` messages.
     Motivation fades back towards each household's own baseline, so it
     needs ongoing input.
  2. **Complaints fade.** A dissatisfied owner falls silent after a mean of
     `duration_months` (or never). Silent, they no longer complain — but
     they no longer speak well of heat pumps either.
  3. **Trigger, then choice.** A household considers a heat pump only when
     something prompts it — boiler replacement, moving, renovation — at
     `trigger_rate` a month (about every 15 years). It then adopts with a
     logistic probability of its motivation, the half-way point lowered for
     higher-`characteristic` households; otherwise it waits for its next
     trigger. Households below `capability_gate` never adopt. A new owner is
     dissatisfied with probability `dissatisfaction.share`.

  Two optional variants of word of mouth, off by default: complex
  contagion (`complex_contagion_beta` > 1, several voices count for more
  than one) and credibility from similar homes (`similar_home_credibility`,
  messages from owners in a different building type count for less).
- `heatpump_sim/simulate.py` — orchestrates a run and records the monthly
  history. `run_dynamics` runs on a given population and network, so sweeps
  can reuse a built network.
- `heatpump_sim/metrics.py` — outcomes: adoption at 5/10/15/25 years, time
  to half of eligible households, install rates, adoption by LSOA type and
  the gap between types, and how clustered owners are on the network.
- `heatpump_sim/visualize.py` — renders the motivation and ownership animation.

## Where the mechanism came from

The model previously moved every household's *opinion* towards its
neighbours' average, with random noise, and installed a heat pump the first
time opinion crossed a threshold. Because adoption was permanent, noise
alone eventually carried most households over the threshold: noise, not the
network or word of mouth, set the result. The current mechanism was
prototyped by Michael Fell in October 2026 to remove that dependence; see
[`analysis/negative_wom/README.md`](analysis/negative_wom/README.md) for the
exploration and [`RESULTS.md`](analysis/negative_wom/RESULTS.md) for its
findings. The package reproduces his prototype run for run. The old model
is on the `negative-wom-exploration` branch.

All dynamics values in `settings.yaml` are placeholders, calibrated only to
year-1 installs of roughly 0.3% of homes a year.

## Everything is a knob

All of the numbers above (trigger rate, motivation and word-of-mouth
rates, dissatisfaction, capability gate, network type/params, months,
random seed) live in `settings.yaml` — edit and rerun to explore
different scenarios.
