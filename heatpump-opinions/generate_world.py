#!/usr/bin/env python3
"""Entry point for stage one: generate a synthetic world (household
locations and characteristics) and write it to a world file.

The simulation then reads that file — set in settings.yaml:

    households:
      location_source: file
      households_source_file: worlds/model_town.csv
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from heatpump_sim.settings import Settings
from heatpump_sim.worldgen import generate_and_write


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", default="settings.yaml", help="Path to settings YAML file")
    parser.add_argument("--out", default=None, help="Output path (default: world_generation.output_file)")
    # Overrides for the knobs worth varying between worlds, so alternative
    # populations can be generated without a bespoke settings file each time.
    parser.add_argument("--seed", type=int, default=None, help="Override world_generation.seed")
    parser.add_argument("--n-households", type=int, default=None, help="Override world_generation.n_households")
    parser.add_argument("--mixing", type=float, default=None,
                        help="Override world_generation.mixing (0 = affluence gradient, 1 = random)")
    parser.add_argument("--grid", type=int, nargs=2, metavar=("ROWS", "COLS"), default=None,
                        help="Override world_generation.grid")
    args = parser.parse_args()

    settings = Settings.load(args.settings)

    overrides = {
        "seed": args.seed,
        "n_households": args.n_households,
        "mixing": args.mixing,
        "grid": args.grid,
    }
    world_cfg = settings.raw.setdefault("world_generation", {})
    for key, value in overrides.items():
        if value is not None:
            world_cfg[key] = value

    out_path = Path(args.out or settings.get("world_generation.output_file", "worlds/model_town.csv"))

    print(f"Generating world -> {out_path}")
    world = generate_and_write(settings, out_path)

    n = len(world["ids"])
    characteristic = world["characteristic"]
    print(f"  households:     {n}")
    print(f"  characteristic: min {characteristic.min():.3f}, "
          f"mean {characteristic.mean():.3f}, max {characteristic.max():.3f}")
    for name in ("lsoa_archetype", "tenure", "building_type"):
        counts = Counter(world["attributes"][name].tolist())
        breakdown = ", ".join(f"{k} {v/n:.0%}" for k, v in sorted(counts.items()))
        print(f"  {name}: {breakdown}")


if __name__ == "__main__":
    main()
