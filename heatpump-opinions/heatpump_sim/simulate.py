"""Top-level orchestration: build the initial state, run the simulation
loop, and record history for visualisation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import numpy as np

from .agents import Households, initialize_households
from .dynamics import step
from .network import build_network
from .settings import Settings


@dataclass
class SimulationResult:
    locations: np.ndarray          # (n, 2)
    characteristic: np.ndarray     # (n,)
    graph: nx.Graph
    opinion_history: np.ndarray    # (T+1, n)
    heatpump_history: np.ndarray   # (T+1, n) bool
    broken_history: np.ndarray     # (T+1, n) bool


def run_simulation(settings: Settings) -> SimulationResult:
    seed = settings.get("simulation.random_seed", 42)
    rng = np.random.default_rng(seed)

    households = initialize_households(settings, rng)
    graph = build_network(households.n, settings, rng)

    n_steps = settings.get("simulation.num_timesteps", 100)

    opinion_history = np.zeros((n_steps + 1, households.n))
    heatpump_history = np.zeros((n_steps + 1, households.n), dtype=bool)
    broken_history = np.zeros((n_steps + 1, households.n), dtype=bool)

    opinion_history[0] = households.opinion
    heatpump_history[0] = households.has_heatpump
    broken_history[0] = households.broken_down

    for t in range(1, n_steps + 1):
        step(households, graph, settings, rng)
        opinion_history[t] = households.opinion
        heatpump_history[t] = households.has_heatpump
        broken_history[t] = households.broken_down

    return SimulationResult(
        locations=households.locations,
        characteristic=households.characteristic,
        graph=graph,
        opinion_history=opinion_history,
        heatpump_history=heatpump_history,
        broken_history=broken_history,
    )


def save_results(result: SimulationResult, results_dir: str | Path) -> None:
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    np.savez(
        results_dir / "history.npz",
        locations=result.locations,
        characteristic=result.characteristic,
        opinion_history=result.opinion_history,
        heatpump_history=result.heatpump_history,
        broken_history=result.broken_history,
    )
    nx.write_graphml(result.graph, results_dir / "network.graphml")
