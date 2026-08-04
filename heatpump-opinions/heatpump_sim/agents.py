"""Household generation: locations, spatially-correlated characteristic,
initial opinions, and initial heat pump ownership."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .settings import Settings


@dataclass
class Households:
    """State for all households. Arrays are all length n, index-aligned."""

    locations: np.ndarray       # (n, 2) float, x/y position in the geographic space
    characteristic: np.ndarray  # (n,) float in [0, 1], demographic/economic number
    opinion: np.ndarray         # (n,) float in [0, 1], opinion of heat pumps
    has_heatpump: np.ndarray    # (n,) bool
    broken_down: np.ndarray     # (n,) bool, True once a heat pump has broken down

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


def load_households_from_file(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Read household locations/characteristics from a CSV with columns:
    id,x,y,characteristic. Returns (locations, characteristic).
    """
    locations, characteristic = [], []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            locations.append((float(row["x"]), float(row["y"])))
            characteristic.append(float(row["characteristic"]))
    return np.array(locations), np.array(characteristic)


def initialize_households(settings: Settings, rng: np.random.Generator) -> Households:
    n = settings.get("households.n_households")
    source = settings.get("households.location_source", "generate")

    if source == "file":
        file_path = settings.get("households.households_source_file")
        locations, characteristic = load_households_from_file(file_path)
        n = len(locations)
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
    )
