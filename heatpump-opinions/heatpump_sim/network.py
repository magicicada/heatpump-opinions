"""Social network construction. The network type is a settings knob so
alternative topologies can be swapped in without touching the rest of the
simulation.

`spatial_kernel` follows the network review in the 26 Aug briefing: ties
are mostly local, with probability decaying exponentially in distance, plus
a fraction of long-range ties placed without regard to geography. Degree
heterogeneity then comes from the kernel and local household density rather
than from preferential attachment. `preferential_attachment` is kept only as
a deliberately unrealistic comparator — at m = 3 it produces hubs whose
single failure dominates a run.

Every edge carries a `kind` attribute: "local" or "long" for the spatial
kernel, "aspatial" for the topology-only builders.
"""
from __future__ import annotations

import warnings

import networkx as nx
import numpy as np

from .settings import Settings

# Pairs further apart than this many decay lengths are never considered for
# a local tie. At 10, exp(-10) ~ 4.5e-5 per pair, and the share of kernel
# mass beyond the cutoff in 2D is (1 + 10) exp(-10) ~ 5e-4.
DEFAULT_CUTOFF_LENGTHS = 10.0

# Distances are computed this many rows at a time and never stored for all
# pairs at once, so memory stays bounded for LSOA-scale worlds (time is
# still O(n^2)).
_BLOCK_ROWS = 256

_ASPATIAL_BUILDERS = {
    "preferential_attachment": lambda n, params, seed: nx.barabasi_albert_graph(
        n, params.get("m", 3), seed=seed
    ),
    "random": lambda n, params, seed: nx.erdos_renyi_graph(
        n, params.get("p", 0.05), seed=seed
    ),
    "small_world": lambda n, params, seed: nx.watts_strogatz_graph(
        n, params.get("k", 4), params.get("p", 0.1), seed=seed
    ),
}


def kernel_params(params: dict) -> dict:
    """Spatial kernel parameters, with defaults filled in and checked.
    Defaults are the briefing's central values."""
    p = {
        "mean_degree": float(params.get("mean_degree", 15)),
        "decay_length_m": float(params.get("decay_length_m", 210.0)),
        "long_range_fraction": float(params.get("long_range_fraction", 0.30)),
        "metres_per_unit": float(params.get("metres_per_unit", 2000.0)),
        "cutoff_lengths": float(params.get("cutoff_lengths", DEFAULT_CUTOFF_LENGTHS)),
    }
    if p["mean_degree"] <= 0:
        raise ValueError(f"network.params.mean_degree must be positive, got {p['mean_degree']}")
    if p["decay_length_m"] <= 0 or p["metres_per_unit"] <= 0 or p["cutoff_lengths"] <= 0:
        raise ValueError(
            "network.params.decay_length_m, metres_per_unit and cutoff_lengths must be positive"
        )
    if not 0.0 <= p["long_range_fraction"] <= 1.0:
        raise ValueError(
            f"network.params.long_range_fraction must be in [0, 1], got {p['long_range_fraction']}"
        )
    return p


def _pair_blocks(locations_m: np.ndarray, cutoff_m: float):
    """Yield (i, j, d) for pairs i < j within cutoff_m of each other, a block
    of rows at a time."""
    n = len(locations_m)
    for start in range(0, n, _BLOCK_ROWS):
        stop = min(start + _BLOCK_ROWS, n)
        diff = locations_m[start:stop, None, :] - locations_m[None, start:, :]
        d = np.sqrt((diff ** 2).sum(axis=-1))
        i, j = np.nonzero(d <= cutoff_m)
        keep = i < j  # both offsets are from `start`, so this is i < j globally
        yield i[keep] + start, j[keep] + start, d[i[keep], j[keep]]


def _kernel_scale(locations_m: np.ndarray, p: dict) -> float:
    """The constant c in p_ij = min(1, c * exp(-d_ij / lambda)), chosen so
    the expected number of local ties per household is
    (1 - long_range_fraction) * mean_degree.

    Since exp(-d / lambda) <= 1, no pair can be clipped while c <= 1, and
    then c = target / sum(kernel) exactly. That is the usual case at
    realistic household densities and needs only a running sum. Only when a
    world is too sparse (c > 1) are the kernel values kept, so c can be
    found by bisection; such a world has few pairs by construction.
    """
    n = len(locations_m)
    lam = p["decay_length_m"]
    cutoff = p["cutoff_lengths"] * lam
    target_edges = (1.0 - p["long_range_fraction"]) * p["mean_degree"] * n / 2.0
    if target_edges == 0:
        return 0.0

    total, n_pairs = 0.0, 0
    for _, _, d in _pair_blocks(locations_m, cutoff):
        total += np.exp(-d / lam).sum()
        n_pairs += len(d)
    if target_edges > n_pairs:
        raise ValueError(
            f"spatial kernel cannot reach mean_degree {p['mean_degree']:g}: only {n_pairs} "
            f"household pairs lie within {p['cutoff_lengths']:g} decay lengths of each other, "
            f"but {target_edges:.0f} local ties are needed. The world is too sparse at "
            f"metres_per_unit = {p['metres_per_unit']:g}; shrink it or lower mean_degree."
        )
    c = target_edges / total
    if c <= 1.0:
        return c

    # Sparse world: expected edge count is monotone in c, so bisect on it.
    kernel = np.concatenate([np.exp(-d / lam) for _, _, d in _pair_blocks(locations_m, cutoff)])
    lo, hi = 0.0, c
    while np.minimum(1.0, hi * kernel).sum() < target_edges:
        lo, hi = hi, 2.0 * hi
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if np.minimum(1.0, mid * kernel).sum() < target_edges:
            lo = mid
        else:
            hi = mid

    saturated = float((hi * kernel >= 1.0).mean())
    if saturated > 0.05:
        warnings.warn(
            f"spatial kernel is saturated: {saturated:.0%} of candidate pairs are tied with "
            f"certainty, so the realised decay is flatter than decay_length_m = {lam:g} m. "
            f"The world is too sparse for this mean_degree at metres_per_unit = "
            f"{p['metres_per_unit']:g}."
        )
    return hi


def local_tie_blocks(locations: np.ndarray, params: dict):
    """Yield (i, j, p_ij) blocks of local tie probabilities,
    p_ij = min(1, c * exp(-d_ij / lambda)), over all pairs within the cutoff.
    The decay length lambda fixes the shape and c the mean degree; see
    `_kernel_scale`."""
    p = kernel_params(params)
    locations_m = np.asarray(locations, dtype=float) * p["metres_per_unit"]
    lam = p["decay_length_m"]
    c = _kernel_scale(locations_m, p)
    for i, j, d in _pair_blocks(locations_m, p["cutoff_lengths"] * lam):
        yield i, j, np.minimum(1.0, c * np.exp(-d / lam))


def _build_spatial_kernel(
    locations: np.ndarray, params: dict, rng: np.random.Generator
) -> nx.Graph:
    p = kernel_params(params)
    n = len(locations)
    graph = nx.Graph()
    graph.add_nodes_from(range(n))

    for i, j, probs in local_tie_blocks(locations, params):
        tied = rng.random(len(probs)) < probs
        graph.add_edges_from(zip(i[tied].tolist(), j[tied].tolist()), kind="local")

    # Long-range ties: a fixed number, placed uniformly at random among
    # pairs not already tied, independent of geography.
    n_long = int(round(p["long_range_fraction"] * p["mean_degree"] * n / 2.0))
    if graph.number_of_edges() + n_long > n * (n - 1) // 2:
        raise ValueError(f"cannot place {n_long} long-range ties among {n} households")
    placed = 0
    while placed < n_long:
        u, v = (int(x) for x in rng.integers(0, n, size=2))
        if u != v and not graph.has_edge(u, v):
            graph.add_edge(u, v, kind="long")
            placed += 1

    return graph


def build_network(
    locations: np.ndarray, settings: Settings, rng: np.random.Generator
) -> nx.Graph:
    network_type = settings.get("network.type", "spatial_kernel")
    params = settings.get("network.params", {}) or {}
    if network_type == "spatial_kernel":
        return _build_spatial_kernel(locations, params, rng)
    builder = _ASPATIAL_BUILDERS.get(network_type)
    if builder is None:
        known = ["spatial_kernel", *_ASPATIAL_BUILDERS]
        raise ValueError(f"Unknown network.type: {network_type!r}; expected one of {known}")
    seed = int(rng.integers(0, 2**31 - 1))
    graph = builder(len(locations), params, seed)
    nx.set_edge_attributes(graph, "aspatial", "kind")
    return graph


def summarise_network(
    graph: nx.Graph,
    locations: np.ndarray,
    cell_ids: np.ndarray | None = None,
    metres_per_unit: float | None = None,
) -> dict:
    """Descriptive statistics of a built network, for run_info.json.

    `cross_cell_share` is the realised share of ties joining households in
    different cells. If it is small, rearranging which archetype sits in
    which cell cannot change much about who hears from whom, and the
    segregation sweep has little to act on.
    """
    degrees = np.array([d for _, d in graph.degree()], dtype=float)
    edges = np.array(list(graph.edges()), dtype=int).reshape(-1, 2)
    kinds = np.array([k for _, _, k in graph.edges(data="kind", default="aspatial")])

    summary = {
        "n_edges": int(graph.number_of_edges()),
        "mean_degree": float(degrees.mean()),
        "degree_std": float(degrees.std()),
        "max_degree": int(degrees.max()),
        "isolated_households": int((degrees == 0).sum()),
        "share_by_kind": {str(k): float((kinds == k).mean()) for k in np.unique(kinds)},
    }
    local = kinds == "local"
    if metres_per_unit is not None and local.any():
        lengths_m = np.linalg.norm(
            locations[edges[local, 0]] - locations[edges[local, 1]], axis=1
        ) * metres_per_unit
        summary["median_local_tie_length_m"] = float(np.median(lengths_m))
    if cell_ids is not None and len(edges):
        summary["cross_cell_share"] = float(
            (cell_ids[edges[:, 0]] != cell_ids[edges[:, 1]]).mean()
        )
    return summary


def expected_cross_cell_share(
    locations: np.ndarray, cell_ids: np.ndarray, params: dict
) -> dict:
    """Expected share of spatial-kernel ties crossing a cell boundary,
    computed from the tie probabilities directly: no network is sampled and
    no dynamics are run. The briefing flags this as one of two quantities to
    compute before spending compute on sweeps.
    """
    p = kernel_params(params)
    total, crossing = 0.0, 0.0
    for i, j, probs in local_tie_blocks(locations, params):
        total += probs.sum()
        crossing += probs[cell_ids[i] != cell_ids[j]].sum()
    local_share = float(crossing / total) if total else 0.0

    # A uniformly random pair crosses a boundary unless both ends share a cell.
    n = len(cell_ids)
    _, counts = np.unique(cell_ids, return_counts=True)
    same_cell_pairs = (counts * (counts - 1) / 2).sum()
    long_share = float(1.0 - same_cell_pairs / (n * (n - 1) / 2))

    f = p["long_range_fraction"]
    return {
        "local": local_share,
        "long": long_share,
        "overall": (1.0 - f) * local_share + f * long_share,
    }
