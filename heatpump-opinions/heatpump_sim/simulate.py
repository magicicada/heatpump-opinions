"""Top-level orchestration: load the population, build the network, run the
monthly dynamics, and record history."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx
import numpy as np

from .agents import AdoptionState, initial_state, load_population
from .dynamics import Contacts, adoption_params, month
from .network import build_network, rewire_preserving_degree
from .settings import Settings


@dataclass
class History:
    """Monthly record of a run: row t is the state after month t (row 0 is
    the starting state)."""

    owner: np.ndarray          # (months+1, n) bool
    dissatisfied: np.ndarray   # (months+1, n) bool
    motivation: np.ndarray     # (months+1, n) float32
    eligible: np.ndarray       # (n,) bool, past the capability gate


@dataclass
class SimulationResult:
    locations: np.ndarray          # (n, 2)
    characteristic: np.ndarray     # (n,)
    graph: nx.Graph                # the network the dynamics ran on
    history: History

    # Descriptive per-household attributes from the world file, if one was
    # loaded (tenure, building_type, lsoa_id, ...). Empty otherwise.
    attributes: dict[str, np.ndarray] = field(default_factory=dict)


def building_type_codes(attributes: dict[str, np.ndarray]) -> np.ndarray | None:
    """Integer code per household for its building type, if the world has one."""
    if "building_type" not in attributes:
        return None
    return np.unique(np.asarray(attributes["building_type"]), return_inverse=True)[1]


def run_dynamics(
    characteristic: np.ndarray,
    edges: np.ndarray,
    building_type: np.ndarray | None,
    params: dict,
    rng: np.random.Generator,
    months: int,
) -> History:
    """Run the monthly dynamics on a fixed population and network. Kept
    separate from run_simulation so sweeps can reuse a built network."""
    n = len(characteristic)
    contacts = Contacts(edges, n, building_type, params["similar_home_credibility"])
    state: AdoptionState = initial_state(characteristic, params, rng)
    eligible = characteristic >= params["capability_gate"]
    half_point = params["half_point"] - params["characteristic_weight"] * characteristic

    owner = np.zeros((months + 1, n), dtype=bool)
    dissatisfied = np.zeros((months + 1, n), dtype=bool)
    motivation = np.zeros((months + 1, n), dtype=np.float32)
    owner[0], dissatisfied[0], motivation[0] = state.owner, state.dissatisfied, state.motivation
    for t in range(1, months + 1):
        month(state, contacts, eligible, half_point, params, rng)
        owner[t], dissatisfied[t], motivation[t] = state.owner, state.dissatisfied, state.motivation
    return History(owner=owner, dissatisfied=dissatisfied, motivation=motivation, eligible=eligible)


def run_simulation(settings: Settings) -> SimulationResult:
    rng = np.random.default_rng(settings.get("simulation.random_seed", 42))
    population = load_population(settings, rng)
    graph = build_network(population.locations, settings, rng)
    if settings.get("network.rewire", False):
        graph = rewire_preserving_degree(graph, rng)
    edges = np.array(list(graph.edges()), dtype=np.int64).reshape(-1, 2)

    history = run_dynamics(
        population.characteristic,
        edges,
        building_type_codes(population.attributes),
        adoption_params(settings),
        rng,
        months=int(settings.get("simulation.months", 300)),
    )
    return SimulationResult(
        locations=population.locations,
        characteristic=population.characteristic,
        graph=graph,
        history=history,
        attributes=population.attributes,
    )


def save_results(result: SimulationResult, results_dir: str | Path) -> None:
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    # World attributes are saved under an attr_ prefix so they never collide
    # with the simulation's own arrays.
    attribute_arrays = {f"attr_{name}": values for name, values in result.attributes.items()}
    np.savez_compressed(
        results_dir / "history.npz",
        locations=result.locations,
        characteristic=result.characteristic,
        owner_history=result.history.owner,
        dissatisfied_history=result.history.dissatisfied,
        motivation_history=result.history.motivation,
        eligible=result.history.eligible,
        **attribute_arrays,
    )
    nx.write_graphml(result.graph, results_dir / "network.graphml")
