"""Household generation: locations, spatially-correlated characteristic,
initial opinions, and initial heat pump ownership."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .settings import Settings
from .world import read_world


@dataclass
class Households:
    """State for all households. Arrays are all length n, index-aligned."""

    locations: np.ndarray       # (n, 2) float, x/y position in the geographic space
    characteristic: np.ndarray  # (n,) float in [0, 1], demographic/economic number
    opinion: np.ndarray         # (n,) float in [0, 1], opinion of heat pumps
    has_heatpump: np.ndarray    # (n,) bool
    broken_down: np.ndarray     # (n,) bool, True once a heat pump has broken down

    # Descriptive attributes carried over from a loaded world file (tenure,
    # building type, ...). Empty for generated populations. The dynamics
    # never read these; they exist so results can be broken down by them.
    attributes: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.locations)


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

    field = np.zeros(len(locations))
    for center, amp in zip(centers, amplitudes):
        d2 = np.sum((locations - center) ** 2, axis=1)
        field += amp * np.exp(-d2 / (2 * length_scale ** 2))

    field += rng.normal(0, noise_std, size=len(locations))

    field_min, field_max = field.min(), field.max()
    return (field - field_min) / (field_max - field_min)


def initialize_households(settings: Settings, rng: np.random.Generator) -> Households:
    n = settings.get("households.n_households")
    source = settings.get("households.location_source", "generate")
    attributes: dict[str, np.ndarray] = {}

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
        locations = world.locations
        characteristic = world.characteristic
        attributes = world.attributes
        # The file is authoritative on population size; n_households is only
        # consulted when generating.
        n = world.n
    elif source == "generate":
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
    else:
        raise ValueError(f"Unknown households.location_source: {source!r}")

    opinion_mean = settings.get("opinions.initial_mean", 0.5)
    opinion_std = settings.get("opinions.initial_std", 0.15)
    opinion = np.clip(rng.normal(opinion_mean, opinion_std, size=n), 0.0, 1.0)

    has_heatpump = np.zeros(n, dtype=bool)
    broken_down = np.zeros(n, dtype=bool)

    initial_fraction = settings.get("heatpumps.initial_fraction", 0.05)
    top_pool_fraction = settings.get("heatpumps.top_pool_fraction", 0.10)

    n_initial = round(n * initial_fraction)
    pool_size = max(n_initial, round(n * top_pool_fraction))
    top_pool = np.argsort(characteristic)[-pool_size:]
    chosen = rng.choice(top_pool, size=n_initial, replace=False)
    has_heatpump[chosen] = True

    return Households(
        locations=locations,
        characteristic=characteristic,
        opinion=opinion,
        has_heatpump=has_heatpump,
        broken_down=broken_down,
        attributes=attributes,
    )
