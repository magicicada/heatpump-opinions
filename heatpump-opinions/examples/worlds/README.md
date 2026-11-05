# Example world files

Committed examples of the [world file format](../../WORLD_FORMAT.md). Unlike
the generated `worlds/` directory (which is gitignored), these are tracked,
so there is always a known-good file to read, test against, or point a
collaborator at.

Run the simulation on any of them:

```bash
python3 run_simulation.py --settings settings.yaml
```

with `households.households_source_file` set to the file you want, or edit
the path in `settings.yaml`.

## The files

| File | Households | Grid | `mixing` | Purpose |
|---|---|---|---|---|
| `tiny_demo.csv` | 40 | 2×2 | 0.3 | Small enough to open and read end to end — the format at a glance |
| `segregated_town.csv` | 200 | 4×4 | 0.0 | Affluence laid out as a clean gradient across the town |
| `mixed_town.csv` | 200 | 4×4 | 1.0 | The same population, neighbourhoods scattered at random |

### The segregated / mixed pair

These two share a seed and differ **only** in `mixing`, so their overall
composition is nearly identical — the same rough split of tenures, building
types and archetypes — and the only meaningful difference is *where*
those households sit relative to one another:

| | `segregated_town` | `mixed_town` |
|---|---|---|
| correlation of `characteristic` with position across town | **+0.69** | **+0.00** |

That is the "how segregated is this town" axis from the 13 Aug discussion —
whether rich and poor neighbourhoods sit in separate blocks or alternate
street by street — isolated from every other difference. Running the same
simulation settings against both is the cleanest way to ask whether spatial
segregation changes adoption dynamics on its own.

A note on the seed: `20` was chosen because its `mixing: 1.0` layout is
*typical* of a random one (correlation ≈ 0, the expected value) rather than
an unlucky draw that still looks gradient-ish. Random layouts vary a fair
amount seed to seed (sd ≈ 0.21 over 60 seeds), so for any real result sweep
seeds rather than relying on one pair. (Before the switch to the six LSOA
types the pair used seed 30, which is no longer typical.)

## Regenerating

Each file is reproducible from the tracked `settings.yaml` plus the flags
below. Regenerate them if the archetype definitions in `settings.yaml`
change, so the examples do not drift from the current model.

```bash
python3 generate_world.py --out examples/worlds/tiny_demo.csv        --n-households 40  --grid 2 2 --seed 1  --mixing 0.3
python3 generate_world.py --out examples/worlds/segregated_town.csv  --n-households 200 --grid 4 4 --seed 20 --mixing 0.0
python3 generate_world.py --out examples/worlds/mixed_town.csv       --n-households 200 --grid 4 4 --seed 20 --mixing 1.0
```

The archetypes are the six LSOA types derived from national data
(`analysis/derive_archetypes.py`); the capability scores that turn tenure,
building type and income into `characteristic` are still placeholders — see
`settings.yaml`.

## LSOA-scale worlds

These examples hold 10–13 households per cell, far fewer than a real LSOA.
At the default `network.params` the 200-household towns still reach the
target degree, but only by tying a much larger share of nearby households
than a real town would; `tiny_demo` is sparse enough that the network
builder warns the kernel is saturated. For runs meant to be read, use
LSOA-sized cells (`world_generation.households_per_cell`,
694 by default: 11,104 households on the 4×4 grid). At ~0.9 MB each these
are not committed; generate them into the gitignored `worlds/`:

```bash
python3 generate_world.py --out worlds/model_town.csv
python3 generate_world.py --out worlds/segregated_town_lsoa.csv --seed 20 --mixing 0.0
python3 generate_world.py --out worlds/mixed_town_lsoa.csv      --seed 20 --mixing 1.0
```

The pair again shares coordinates, so it pairs as tightly as the small one.
Correlation of `characteristic` with position across town is +0.71 for the
segregated world and +0.00 for the mixed one. A single 25-year run takes
about 20 s with `--no-animations`, most of it building the network and
saving the history; rendering the animation adds a few minutes.
