"""Monthly adoption dynamics: experience-based word of mouth, then trigger
and choice.

One step is one month. Each month:

1. Word of mouth. Only owners talk. Each owner talks to each contact with
   probability `contact_rate`. A satisfied owner's message moves the
   listener's motivation a fraction `message_strength` of the way to 1; a
   complaining owner's message counts as `dissatisfaction.weight` messages
   pushing it towards 0. Before messages land, motivation relaxes back
   towards the household's own baseline at rate `memory`, so what people
   hear fades unless it is renewed.
2. Complaints fade. A complaining owner falls silent with probability
   1 / `duration_months` (never, if duration is null). They stay
   dissatisfied: a silent dissatisfied owner no longer complains, but no
   longer speaks well of heat pumps either.
3. Trigger and choice. A non-owner past the capability gate has a trigger
   (boiler replacement, moving, renovation) with probability `trigger_rate`.
   When triggered it adopts with probability
       logistic((motivation - half_point_i) / slope),
       half_point_i = half_point - characteristic_weight * characteristic,
   and otherwise waits for its next trigger. A new owner is dissatisfied
   with probability `dissatisfaction.share`.

Two optional word-of-mouth variants, both off by default:

A. Complex contagion (`complex_contagion_beta` > 1). Hearing from several
   different owners in a month counts for more than hearing from one:
       effective messages = messages * (distinct owners / reference) ** (beta - 1)
B. Credibility from similar homes (`similar_home_credibility` = b > 0). A
   message from an owner in a different building type counts (1 - b).

This is the mechanism prototyped in analysis/negative_wom/proto3.py on the
negative-wom-exploration branch (commit 88b8102); random draws are made in
the same order, so a run reproduces that script exactly.
"""
from __future__ import annotations

import numpy as np

from .agents import AdoptionState
from .settings import Settings


def adoption_params(settings: Settings) -> dict:
    """Every dynamics parameter from settings.yaml, defaults filled in and checked."""
    duration = settings.get("dissatisfaction.duration_months")
    p = {
        "initial_fraction": float(settings.get("adoption.initial_fraction", 0.01)),
        "initial_owners": settings.get("adoption.initial_owners", "top"),
        "top_pool_fraction": float(settings.get("adoption.top_pool_fraction", 0.10)),
        "trigger_rate": float(settings.get("adoption.trigger_rate", 1 / 180)),
        "capability_gate": float(settings.get("adoption.capability_gate", 0.30)),
        "half_point": float(settings.get("adoption.half_point", 0.8)),
        "characteristic_weight": float(settings.get("adoption.characteristic_weight", 0.2)),
        "slope": float(settings.get("adoption.slope", 0.07)),
        "baseline_mean": float(settings.get("motivation.baseline_mean", 0.3)),
        "baseline_sd": float(settings.get("motivation.baseline_sd", 0.15)),
        "memory": float(settings.get("motivation.memory", 0.05)),
        "contact_rate": float(settings.get("word_of_mouth.contact_rate", 0.72)),
        "message_strength": float(settings.get("word_of_mouth.message_strength", 0.06)),
        "beta": float(settings.get("word_of_mouth.complex_contagion_beta", 1.0)),
        "beta_reference": float(settings.get("word_of_mouth.complex_contagion_reference", 2.0)),
        "similar_home_credibility": float(settings.get("word_of_mouth.similar_home_credibility", 0.0)),
        "dissatisfied_share": float(settings.get("dissatisfaction.share", 0.0)),
        "complaint_weight": float(settings.get("dissatisfaction.weight", 1.0)),
        "duration_months": np.inf if duration is None else float(duration),
    }
    for key in ("initial_fraction", "top_pool_fraction", "trigger_rate", "memory", "contact_rate",
                "message_strength", "similar_home_credibility", "dissatisfied_share"):
        if not 0.0 <= p[key] <= 1.0:
            raise ValueError(f"{key} must be in [0, 1], got {p[key]}")
    if p["beta"] < 1.0:
        raise ValueError(f"word_of_mouth.complex_contagion_beta must be >= 1, got {p['beta']}")
    if p["slope"] <= 0 or p["duration_months"] <= 0:
        raise ValueError("adoption.slope and dissatisfaction.duration_months must be positive")
    return p


class Contacts:
    """The network as directed arrays (each tie both ways), with each
    message's credibility weight precomputed."""

    def __init__(self, edges: np.ndarray, n: int, building_type: np.ndarray | None,
                 similar_home_credibility: float):
        edges = np.asarray(edges, dtype=np.int64).reshape(-1, 2)
        self.n = n
        self.src = np.concatenate([edges[:, 0], edges[:, 1]])
        self.dst = np.concatenate([edges[:, 1], edges[:, 0]])
        if similar_home_credibility > 0:
            if building_type is None:
                raise ValueError("similar_home_credibility needs a world file with a building_type column")
            same = building_type[self.src] == building_type[self.dst]
            self.credibility = np.where(same, 1.0, 1.0 - similar_home_credibility)
        else:
            self.credibility = np.ones(len(self.src))

    def heard(self, messages: np.ndarray, p: dict) -> np.ndarray:
        """Effective number of messages each household receives, from the
        indices of the directed ties that carried one this month. A tie
        carries at most one message a month, so the number of messages is
        also the number of distinct owners heard from (credibility-weighted)."""
        n_msg = np.bincount(self.dst[messages], weights=self.credibility[messages], minlength=self.n)
        if p["beta"] == 1.0:
            return n_msg
        return n_msg * (n_msg / p["beta_reference"]) ** (p["beta"] - 1)


def month(state: AdoptionState, contacts: Contacts, eligible: np.ndarray,
          half_point: np.ndarray, p: dict, rng: np.random.Generator) -> None:
    """Advance the adoption state by one month, in place."""
    n = contacts.n

    # 1. Word of mouth.
    satisfied = state.owner & ~state.dissatisfied
    talking = np.nonzero((satisfied | state.complaining)[contacts.src])[0]
    talking = talking[rng.random(len(talking)) < p["contact_rate"]]
    positive = satisfied[contacts.src[talking]]
    keep = 1.0 - p["message_strength"]
    m = state.motivation + p["memory"] * (state.baseline - state.motivation)
    m = 1 - (1 - m) * keep ** contacts.heard(talking[positive], p)
    m = m * keep ** (p["complaint_weight"] * contacts.heard(talking[~positive], p))
    state.motivation = m

    # 2. Complaints fade.
    stop = 0.0 if np.isinf(p["duration_months"]) else 1.0 / p["duration_months"]
    state.complaining &= ~(rng.random(n) < stop)

    # 3. Trigger and choice.
    triggered = ~state.owner & eligible & (rng.random(n) < p["trigger_rate"])
    adopt_prob = 1 / (1 + np.exp(-(m - half_point) / p["slope"]))
    new = triggered & (rng.random(n) < adopt_prob)
    state.owner |= new
    new_dissatisfied = new & (rng.random(n) < p["dissatisfied_share"])
    state.dissatisfied |= new_dissatisfied
    state.complaining |= new_dissatisfied
