"""Outcome measures computed from a run's history."""
from __future__ import annotations

import numpy as np

from .simulate import History

# Months at which outcomes are reported by default (5, 10, 15, 25 years).
CHECKPOINTS = (60, 120, 180, 300)


def adoption_curve(history: History) -> np.ndarray:
    """Share of all households with a heat pump, per month."""
    return history.owner.mean(axis=1)


def months_to(curve: np.ndarray, level: float) -> float | None:
    """First month at which `curve` reaches `level`, linearly interpolated.
    None if never reached."""
    above = np.nonzero(curve >= level)[0]
    if len(above) == 0:
        return None
    t = int(above[0])
    if t == 0:
        return 0.0
    y0, y1 = curve[t - 1], curve[t]
    return (t - 1) + ((level - y0) / (y1 - y0) if y1 != y0 else 0.0)


def adoption_by_type(owner: np.ndarray, eligible: np.ndarray, types: np.ndarray,
                     min_eligible: int = 50) -> dict[str, float]:
    """Share of *eligible* households with a heat pump, per LSOA type (or any
    other grouping). Types with fewer than `min_eligible` eligible households
    are left out, since their shares are too noisy to compare."""
    out = {}
    for t in np.unique(types):
        mask = (types == t) & eligible
        if mask.sum() > min_eligible:
            out[str(t)] = float(owner[mask].mean())
    return out


def type_range(by_type: dict[str, float]) -> float:
    """Gap between the highest- and lowest-adopting types."""
    return max(by_type.values()) - min(by_type.values()) if by_type else float("nan")


def owner_clustering(owner: np.ndarray, edges: np.ndarray) -> float:
    """Share of an owner's network neighbours who are owners, over the share
    expected if owners were scattered at random (1 = no clustering)."""
    n = len(owner)
    u, v = edges[:, 0], edges[:, 1]
    degree = np.bincount(edges.ravel(), minlength=n)
    owner_neighbours = (np.bincount(u, weights=owner[v], minlength=n)
                        + np.bincount(v, weights=owner[u], minlength=n))
    return float((owner_neighbours[owner] / np.maximum(degree[owner], 1)).mean() / owner.mean())


def summarise(history: History, types: np.ndarray | None = None,
              checkpoints=CHECKPOINTS) -> dict:
    """Headline outcomes of a run, for run_info.json and sweeps."""
    curve = adoption_curve(history)
    months = len(curve) - 1
    checkpoints = [t for t in checkpoints if t <= months]
    eligible_curve = history.owner[:, history.eligible].mean(axis=1)
    yearly = np.diff(curve[::12]) * 100

    row = {f"adoption_m{t}": float(curve[t]) for t in checkpoints}
    row["final_adoption"] = float(curve[-1])
    row["final_dissatisfied"] = float(history.dissatisfied[-1].mean())
    half = months_to(eligible_curve, 0.5)
    row["months_to_half_of_eligible"] = half
    if len(yearly):
        row["first_year_installs_pct"] = float(yearly[0])
        row["peak_year_installs_pct"] = float(yearly.max())
        row["peak_year"] = int(yearly.argmax()) + 1
    if types is not None:
        for t in checkpoints:
            by = adoption_by_type(history.owner[t], history.eligible, types)
            row[f"type_range_m{t}"] = type_range(by)
            row.update({f"adoption_m{t}_{name}": share for name, share in by.items()})
    return row
