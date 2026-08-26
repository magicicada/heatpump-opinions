# Heat Pump Adoption Simulation

Agent-based simulation of opinion formation and heat pump adoption over a
social network of households.

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
    history.npz         raw arrays (opinions, ownership, breakdowns, world attributes)
    network.graphml     the social network
    run_info.json       what produced this run — world, seed, parameters, outcome
    *.gif               animations
```

Useful flags: `--world <path>` and `--seed <n>` to override the settings for
one run, `--run-name` to name the output directory, and `--no-animations`
to skip GIF rendering (which dominates runtime).

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
segregated the town is. Because both hold the same number of households, a
given seed produces the same initial opinions and the same social network in
both, so the pairing is tight and the only difference is who lives where.
Writes a per-run CSV and a summary figure to `analysis/`.

The two stages are deliberately separate: assumptions about *who lives
where* can be changed, swapped for real data, or swept without touching the
adoption dynamics, and every run can be traced back to the exact population
it used. The world file is the only contract between them — see
[WORLD_FORMAT.md](WORLD_FORMAT.md). To skip stage one and generate
households in-process instead, set `households.location_source: generate`.

## Structure

- `settings.yaml` — every tunable parameter for both stages (household
  count, network type, opinion dynamics rates, thresholds, world
  generation, output paths).
- `generate_world.py` / `heatpump_sim/worldgen.py` — **stage one**. Tiles a
  model town with a grid of LSOA-like cells, assigns each an archetype
  (distributions over tenure, building type and income decile), draws
  households inside it and composes their `characteristic` from the drawn
  attributes. The `world_generation.mixing` knob runs from a clean
  affluence gradient across the town (`0`) to archetypes scattered at
  random (`1`) — the "how segregated is this town" axis.
- `heatpump_sim/world.py` — the world file format: schema, reader, writer,
  validation. See [WORLD_FORMAT.md](WORLD_FORMAT.md).
- `heatpump_sim/agents.py` — loads a world file, or (in `generate` mode)
  synthesises locations and a spatially-correlated `characteristic`
  directly, then sets initial opinions and heat pump ownership.
- `heatpump_sim/network.py` — builds the social network. Currently
  supports `preferential_attachment` (Barabási–Albert), `random`
  (Erdős–Rényi), and `small_world` (Watts–Strogatz), selected via
  `network.type`.
- `heatpump_sim/dynamics.py` — per-timestep update:
  1. Each household's opinion moves toward its network neighbours' mean
     opinion, plus a steady increase if it owns a working heat pump, plus
     noise.
  2. A small fraction of heat pump owners (`heatpumps.breakdown_rate`)
     break down each turn: their `broken_down` flag is set, opinion is
     forced to 0, and they're excluded from all further opinion updates —
     so it can never rise again.
  3. Any household without a heat pump whose opinion has crossed its
     *effective* install threshold gets one installed. The effective
     threshold is `install_threshold - characteristic_weight * characteristic`,
     so higher-characteristic households (more economic capacity) need less
     opinion before they act on it — the `characteristic` was otherwise only
     used once, to pick the initial owners, so this brings it back into the
     ongoing adoption decision instead of leaving it inert after t=0.
     Households with `characteristic` below `characteristic_gate` are
     structurally excluded regardless: no opinion, however high, lets them
     adopt. This models a hard barrier (e.g. renting, flats, no financial
     means) as distinct from the graded discount above.
- `heatpump_sim/simulate.py` — orchestrates a run and records full history.
- `heatpump_sim/visualize.py` — renders the two animations.

## A note on `opinions.noise_std`

Non-owners' opinions relax toward the average opinion of their network
neighbours. With low noise this settles into a stable local average that,
for most households, never gets close to the 0.95 install threshold
unless nearly all of a household's neighbours already have high opinions —
a bootstrap-percolation-style stall where adoption never takes off. Raising
`noise_std` (default 0.10) adds enough random fluctuation that some
households occasionally cross the threshold by chance, become new
"champions," and reinforce their neighbourhood — producing the classic
S-curve adoption pattern. Lower it if you want to study the stalled regime
instead.

## Everything is a knob

All of the numbers above (household count, initial adoption fraction,
breakdown rate, install threshold, opinion rates, network type/params,
timesteps, random seed) live in `settings.yaml` — edit and rerun to explore
different scenarios.
