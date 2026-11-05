"""Households: the population (locations, characteristic, descriptive
attributes) and their adoption state (motivation, ownership,
dissatisfaction)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .settings import Settings
from .world import read_world


@dataclass
class Population:
    """Who lives where. Fixed over a run. Arrays are length n, index-aligned."""

    locations: np.ndarray       # (n, 2) float, x/y position in the geographic space
    characteristic: np.ndarray  # (n,) float in [0, 1], demographic/economic capability

    # Descriptive attributes carried over from a loaded world file (tenure,
    # building type, ...). Empty for generated populations.
    attributes: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.locations)


@dataclass
class AdoptionState:
    """Everything that changes over a run."""

    baseline: np.ndarray       # (n,) motivation each household relaxes back to
    motivation: np.ndarray     # (n,) current motivation in [0, 1]
    owner: np.ndarray          # (n,) bool, has a heat pump
    dissatisfied: np.ndarray   # (n,) bool, owner with a bad experience
    complaining: np.ndarray    # (n,) bool, dissatisfied owner still talking negatively


def _generate_locations(n: int, space_size: tuple[float, float], rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(low=[0, 0], high=space_size, size=(n, 2))


def _generate_correlated_characteristic(
    locations: np.ndarray,
    n_centers: int,
    length_scale: float,
    noise_std: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Build a smooth spatial field by summing random-amplitude Gaussian
    "hotspots", then adding noise. Because the underlying field is smooth,
    nearby households end up with correlated values before the field is
    rescaled into [0, 1].
    """
    lo = locations.min(axis=0)
    hi = locations.max(axis=0)
    centers = rng.uniform(low=lo, high=hi, size=(n_centers, 2))
    amplitudes = rng.normal(0, 1, size=n_centers)

    values = np.zeros(len(locations))
    for center, amp in zip(centers, amplitudes):
        d2 = np.sum((locations - center) ** 2, axis=1)
        values += amp * np.exp(-d2 / (2 * length_scale ** 2))

    values += rng.normal(0, noise_std, size=len(locations))

    v_min, v_max = values.min(), values.max()
    return (values - v_min) / (v_max - v_min)


def load_population(settings: Settings, rng: np.random.Generator) -> Population:
    """Read the world file, or (in `generate` mode) synthesise locations and a
    spatially correlated characteristic. Only `generate` mode draws from rng."""
    source = settings.get("households.location_source", "file")

    if source == "file":
        file_path = settings.get("households.households_source_file")
        if not file_path:
            raise ValueError(
                "households.location_source is 'file' but "
                "households.households_source_file is not set"
            )
        if not Path(file_path).exists():
            raise FileNotFoundError(
                f"World file {file_path!r} not found. Generate one first:\n"
                f"    python3 generate_world.py --settings <settings.yaml>\n"
                f"or set households.location_source to 'generate'."
            )
        world = read_world(file_path)
        return Population(world.locations, world.characteristic, world.attributes)

    if source == "generate":
        n = settings.get("households.n_households")
        space_size = tuple(settings.get("households.space_size", [1.0, 1.0]))
        locations = _generate_locations(n, space_size, rng)
        field_cfg = settings.get("households.characteristic_field", {})
        characteristic = _generate_correlated_characteristic(
            locations,
            n_centers=field_cfg.get("n_centers", 8),
            length_scale=field_cfg.get("length_scale", 0.3),
            noise_std=field_cfg.get("noise_std", 0.15),
            rng=rng,
        )
        return Population(locations, characteristic)

    raise ValueError(f"Unknown households.location_source: {source!r}")


def initial_state(
    characteristic: np.ndarray, params: dict, rng: np.random.Generator
) -> AdoptionState:
    """Baseline motivations, the first owners and which of them start
    dissatisfied. `params` is the dict from dynamics.adoption_params().

    The first owners are drawn from the top `top_pool_fraction` of households
    by characteristic ("top"), or from everyone ("random").
    """
    n = len(characteristic)
    baseline = np.clip(rng.normal(params["baseline_mean"], params["baseline_sd"], n), 0, 1)

    if params["initial_owners"] == "top":
        pool = np.argsort(characteristic)[-round(params["top_pool_fraction"] * n):]
    elif params["initial_owners"] == "random":
        pool = np.arange(n)
    else:
        raise ValueError(f"adoption.initial_owners must be 'top' or 'random', got {params['initial_owners']!r}")
    owner = np.zeros(n, dtype=bool)
    owner[rng.choice(pool, round(params["initial_fraction"] * n), replace=False)] = True

    dissatisfied = owner & (rng.random(n) < params["dissatisfied_share"])
    return AdoptionState(
        baseline=baseline,
        motivation=baseline.copy(),
        owner=owner,
        dissatisfied=dissatisfied,
        complaining=dissatisfied.copy(),
    )
