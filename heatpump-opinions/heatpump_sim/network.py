"""Social network construction. The network type is a settings knob so
alternative topologies can be swapped in without touching the rest of the
simulation."""
from __future__ import annotations

import networkx as nx
import numpy as np

from .settings import Settings

_BUILDERS = {
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


def build_network(n: int, settings: Settings, rng: np.random.Generator) -> nx.Graph:
    network_type = settings.get("network.type", "preferential_attachment")
    params = settings.get("network.params", {}) or {}
    builder = _BUILDERS.get(network_type)
    if builder is None:
        raise ValueError(f"Unknown network.type: {network_type!r}")
    seed = int(rng.integers(0, 2**31 - 1))
    return builder(n, params, seed)
