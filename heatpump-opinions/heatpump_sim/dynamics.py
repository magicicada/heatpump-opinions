"""Per-timestep decision-making (opinion update + breakdowns) and the
subsequent heat pump installation step."""
from __future__ import annotations

import networkx as nx
import numpy as np

from .agents import Households
from .settings import Settings


def opinion_update_step(
    households: Households,
    graph: nx.Graph,
    settings: Settings,
    rng: np.random.Generator,
) -> None:
    """Update opinions in place based on social influence from network
    neighbours and steady self-increase for working heat pump owners.
    Then roll the dice on breakdowns: newly-broken households have their
    breakdown flag set and their opinion locked at 0.
    """
    social_rate = settings.get("opinions.social_influence_rate", 0.15)
    self_increase = settings.get("opinions.self_increase_rate", 0.03)
    noise_std = settings.get("opinions.noise_std", 0.02)
    breakdown_rate = settings.get("heatpumps.breakdown_rate", 0.01)

    opinion = households.opinion
    new_opinion = opinion.copy()

    for i in range(households.n):
        if households.broken_down[i]:
            continue  # opinion permanently locked at 0

        neighbors = list(graph.neighbors(i))
        neighbor_mean = opinion[neighbors].mean() if neighbors else opinion[i]

        delta = social_rate * (neighbor_mean - opinion[i])
        if households.has_heatpump[i]:
            delta += self_increase
        delta += rng.normal(0, noise_std)

        new_opinion[i] = np.clip(opinion[i] + delta, 0.0, 1.0)

    households.opinion = new_opinion

    # Breakdowns: only working owners (has a heat pump, not already broken) are at risk.
    at_risk = np.where(households.has_heatpump & ~households.broken_down)[0]
    breaks = rng.random(len(at_risk)) < breakdown_rate
    newly_broken = at_risk[breaks]

    households.broken_down[newly_broken] = True
    households.opinion[newly_broken] = 0.0


def installation_step(households: Households, settings: Settings) -> None:
    """Households without a heat pump whose opinion has crossed their
    effective threshold get one installed. The effective threshold is the
    base install_threshold discounted by characteristic_weight * characteristic,
    so higher-characteristic (e.g. wealthier) households need less opinion
    to act on before they can adopt.
    """
    threshold = settings.get("heatpumps.install_threshold", 0.95)
    characteristic_weight = settings.get("heatpumps.characteristic_weight", 0.0)

    effective_threshold = threshold - characteristic_weight * households.characteristic
    new_installs = ~households.has_heatpump & (households.opinion > effective_threshold)
    households.has_heatpump[new_installs] = True


def step(
    households: Households,
    graph: nx.Graph,
    settings: Settings,
    rng: np.random.Generator,
) -> None:
    opinion_update_step(households, graph, settings, rng)
    installation_step(households, settings)
