"""Synthetic world generation.

Builds a population of households on an abstract "model town" and writes it
as a world file (see `world.py` for the format). This is stage one of two:
nothing here knows anything about opinions, heat pumps or time.

The town is a grid of cells standing in for LSOAs. Each cell is assigned an
*archetype* — a bundle of distributions over tenure, building type and
income decile — and households drawn inside that cell inherit those
distributions. Their `characteristic` is then composed from the drawn
attributes.

The layout knob is `mixing`, in [0, 1]:

    mixing = 0   archetypes laid out as a clean affluence gradient across
                 the grid (most deprived one corner, most affluent the
                 opposite)
    mixing = 1   archetypes scattered across cells at random

Intermediate values interpolate, which is the "how segregated is this town"
axis: whether rich and poor neighbourhoods sit in separate blocks or
alternate street by street. Nothing else about the model changes with it,
so it can be swept like any other parameter.

NOTE: the archetype definitions in settings.yaml are placeholders standing
in for real LSOA data (tenure / building type / income decile by LSOA).
They are shaped to be replaced wholesale once that data is available, with
no change to this code.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from .settings import Settings
from .world import write_world


def _normalised_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("capability weights must sum to a positive number")
    return {k: v / total for k, v in weights.items()}


def _sample_categorical(
    mix: dict[str, float], size: int, rng: np.random.Generator
) -> np.ndarray:
    """Draw `size` labels from a {label: probability} mapping."""
    labels = list(mix.keys())
    probs = np.array([mix[k] for k in labels], dtype=float)
    if probs.sum() <= 0:
        raise ValueError(f"category mix must have positive weights, got {mix}")
    probs = probs / probs.sum()
    return rng.choice(labels, size=size, p=probs)


def _assign_archetypes_to_cells(
    archetypes: list[dict],
    n_cells: int,
    grid: tuple[int, int],
    mixing: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Decide which archetype each grid cell takes.

    Cells are scored by blending their position along the grid diagonal with
    a random draw, then ranked; archetypes are handed out in ascending
    affluence order. At mixing=0 the ranking is purely positional (a clean
    gradient); at mixing=1 it is pure noise (random placement).
    """
    rows, cols = grid

    # Positional score: 0 at one corner, 1 at the opposite corner.
    denom = max((rows - 1) + (cols - 1), 1)
    gradient = np.array(
        [(r + c) / denom for r in range(rows) for c in range(cols)], dtype=float
    )
    noise = rng.random(n_cells)
    score = (1.0 - mixing) * gradient + mixing * noise

    # Archetypes ordered poorest-first, by mean income decile, so the order
    # they happen to appear in the settings file does not matter.
    order = sorted(
        range(len(archetypes)),
        key=lambda i: float(np.mean(archetypes[i]["income_decile_range"])),
    )

    # How many cells each archetype gets, by share, summing exactly to n_cells.
    shares = np.array([archetypes[i].get("share", 1.0) for i in order], dtype=float)
    shares = shares / shares.sum()
    counts = np.floor(shares * n_cells).astype(int)
    while counts.sum() < n_cells:  # hand out rounding remainder to the largest shares
        counts[np.argmax(shares - counts / max(n_cells, 1))] += 1

    ranked_cells = np.argsort(score)  # lowest score -> poorest archetype
    assignment = np.empty(n_cells, dtype=int)
    cursor = 0
    for archetype_index, count in zip(order, counts):
        assignment[ranked_cells[cursor : cursor + count]] = archetype_index
        cursor += count

    return assignment


def _characteristic_from_attributes(
    income_decile: np.ndarray,
    tenure: np.ndarray,
    building_type: np.ndarray,
    capability: dict,
    rng: np.random.Generator,
) -> np.ndarray:
    """Compose the [0, 1] capability number from drawn attributes.

    A weighted average of three sub-scores plus noise. Weights are
    normalised so the result sits in [0, 1] before noise is added.
    """
    weights = _normalised_weights(capability.get("weights", {}))
    tenure_scores = capability.get("tenure_scores", {})
    building_scores = capability.get("building_scores", {})

    unknown_tenure = set(np.unique(tenure)) - set(tenure_scores)
    if unknown_tenure:
        raise ValueError(f"no capability score defined for tenure(s): {sorted(unknown_tenure)}")
    unknown_building = set(np.unique(building_type)) - set(building_scores)
    if unknown_building:
        raise ValueError(f"no capability score defined for building type(s): {sorted(unknown_building)}")

    income_score = (income_decile.astype(float) - 1.0) / 9.0  # deciles 1-10 -> [0, 1]
    tenure_score = np.array([tenure_scores[t] for t in tenure], dtype=float)
    building_score = np.array([building_scores[b] for b in building_type], dtype=float)

    characteristic = (
        weights.get("income", 0.0) * income_score
        + weights.get("tenure", 0.0) * tenure_score
        + weights.get("building", 0.0) * building_score
    )
    characteristic += rng.normal(0, capability.get("noise_std", 0.0), size=len(characteristic))
    return np.clip(characteristic, 0.0, 1.0)


def generate_world(settings: Settings) -> dict:
    """Generate a synthetic population. Returns the pieces `write_world`
    needs, so callers can write it out or inspect it in memory."""
    cfg_seed = settings.get("world_generation.seed", 7)
    rng = np.random.default_rng(cfg_seed)

    n_households = settings.get("world_generation.n_households", 400)
    space_size = tuple(settings.get("world_generation.space_size", [1.0, 1.0]))
    grid = tuple(settings.get("world_generation.grid", [4, 4]))
    mixing = float(settings.get("world_generation.mixing", 0.3))
    archetypes = settings.get("world_generation.archetypes", [])
    capability = settings.get("world_generation.capability", {})

    if not archetypes:
        raise ValueError("world_generation.archetypes is empty — nothing to generate from")
    if not 0.0 <= mixing <= 1.0:
        raise ValueError(f"world_generation.mixing must be in [0, 1], got {mixing}")

    rows, cols = grid
    n_cells = rows * cols
    # households_per_cell, when set, fixes the size of each LSOA-like cell
    # and takes precedence over n_households, so the grid can be resized
    # without the cells thinning out.
    households_per_cell = settings.get("world_generation.households_per_cell")
    if households_per_cell is not None:
        n_households = n_cells * int(households_per_cell)
    if n_cells > n_households:
        raise ValueError(
            f"grid has {n_cells} cells but only {n_households} households — "
            "increase n_households or shrink the grid"
        )

    cell_archetype = _assign_archetypes_to_cells(archetypes, n_cells, grid, mixing, rng)

    # Households split as evenly as possible across cells; real LSOAs are
    # built to hold similar populations, so equal-ish is a fair stand-in.
    per_cell = np.full(n_cells, n_households // n_cells, dtype=int)
    per_cell[: n_households % n_cells] += 1

    cell_width = space_size[0] / cols
    cell_height = space_size[1] / rows

    xs, ys = [], []
    lsoa_ids, archetype_names = [], []
    income_deciles, tenures, building_types = [], [], []

    for cell in range(n_cells):
        count = per_cell[cell]
        if count == 0:
            continue
        row, col = divmod(cell, cols)
        archetype = archetypes[cell_archetype[cell]]

        xs.append(rng.uniform(col * cell_width, (col + 1) * cell_width, size=count))
        ys.append(rng.uniform(row * cell_height, (row + 1) * cell_height, size=count))

        lsoa_ids.append(np.full(count, f"C{cell:03d}"))
        archetype_names.append(np.full(count, archetype["name"]))

        low, high = archetype["income_decile_range"]
        income_deciles.append(rng.integers(low, high + 1, size=count))
        tenures.append(_sample_categorical(archetype["tenure_mix"], count, rng))
        building_types.append(_sample_categorical(archetype["building_mix"], count, rng))

    locations = np.column_stack([np.concatenate(xs), np.concatenate(ys)])
    income_decile = np.concatenate(income_deciles)
    tenure = np.concatenate(tenures)
    building_type = np.concatenate(building_types)

    characteristic = _characteristic_from_attributes(
        income_decile, tenure, building_type, capability, rng
    )

    return {
        "ids": np.arange(len(locations)),
        "locations": locations,
        "characteristic": characteristic,
        "attributes": {
            "lsoa_id": np.concatenate(lsoa_ids),
            "lsoa_archetype": np.concatenate(archetype_names),
            "income_decile": income_decile,
            "tenure": tenure,
            "building_type": building_type,
        },
        "metadata": {
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "seed": cfg_seed,
            "grid": f"{rows}x{cols}",
            "mixing": mixing,
            "space_size": f"{space_size[0]}x{space_size[1]}",
            "archetypes": ", ".join(a["name"] for a in archetypes),
        },
    }


def generate_and_write(settings: Settings, out_path) -> dict:
    world = generate_world(settings)
    write_world(
        out_path,
        ids=world["ids"],
        locations=world["locations"],
        characteristic=world["characteristic"],
        attributes=world["attributes"],
        metadata=world["metadata"],
    )
    return world
