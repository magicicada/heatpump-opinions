# Heat Pump Adoption Simulation

Agent-based simulation of opinion formation and heat pump adoption over a
social network of households.

## Run it

```bash
python3 run_simulation.py --settings settings.yaml
```

Outputs land in `results/`: `history.npz` (raw arrays), `network.graphml`
(the social network), and `opinion_animation.gif` / `heatpump_animation.gif`.

## Structure

- `settings.yaml` — every tunable parameter (household count, network type,
  opinion dynamics rates, thresholds, output paths).
- `heatpump_sim/agents.py` — generates household locations and a
  demographic/economic `characteristic` in [0, 1] that's spatially
  correlated (built from a handful of random Gaussian "hotspots" summed
  over space, then noised and rescaled). Can instead load
  locations/characteristics from a CSV (`households.location_source: file`,
  columns `id,x,y,characteristic`).
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
  3. Any household without a heat pump whose opinion has crossed
     `heatpumps.install_threshold` gets one installed.
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
