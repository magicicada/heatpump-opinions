"""Animated visualisation of a run: motivation (continuous colour scale) and
heat pump ownership side by side over the geographic layout of households."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.collections import LineCollection

from .simulate import SimulationResult

# Ownership categories, in drawing order.
OWNERSHIP = (
    ("Cannot adopt (below gate)", "#e4e3dd"),
    ("No heat pump", "#a3a29c"),
    ("Satisfied owner", "#2a78d6"),
    ("Dissatisfied owner", "#eb6834"),
)


def _draw_network_edges(ax, locations: np.ndarray, graph: nx.Graph) -> None:
    # One LineCollection rather than a plot call per edge: LSOA-scale worlds
    # have tens of thousands of edges. Edges fade as their number grows so
    # the plot does not turn solid grey.
    edges = np.array(list(graph.edges()), dtype=int).reshape(-1, 2)
    segments = np.stack([locations[edges[:, 0]], locations[edges[:, 1]]], axis=1)
    alpha = min(0.25, 0.25 * 1000 / max(len(edges), 1))
    ax.add_collection(LineCollection(segments, colors="grey", linewidths=0.4, alpha=alpha, zorder=1))


def _marker_size(n: int) -> float:
    """Marker area that keeps households distinguishable: 60 up to a few
    hundred households, shrinking in proportion beyond that."""
    return min(60.0, 60.0 * 400 / n)


def _ownership_colours(result: SimulationResult, t: int) -> np.ndarray:
    h = result.history
    category = np.where(h.eligible, 1, 0)
    category = np.where(h.owner[t], 2, category)
    category = np.where(h.dissatisfied[t], 3, category)
    return np.array([colour for _, colour in OWNERSHIP])[category]


def animate(result: SimulationResult, out_path: str | Path, fps: int = 8, every_months: int = 3) -> None:
    """Motivation and ownership panels, stepping through the same month
    together, one frame per `every_months` months."""
    h = result.history
    n = len(result.locations)
    frames = list(range(0, len(h.owner), every_months))
    if frames[-1] != len(h.owner) - 1:
        frames.append(len(h.owner) - 1)
    scatter_kw = dict(s=_marker_size(n), edgecolors="black", linewidths=0.4 if n <= 1000 else 0.0, zorder=2)

    fig, (ax_m, ax_o) = plt.subplots(1, 2, figsize=(13, 6))
    x, y = result.locations[:, 0], result.locations[:, 1]

    _draw_network_edges(ax_m, result.locations, result.graph)
    m_scatter = ax_m.scatter(x, y, c=h.motivation[0], cmap="RdYlGn", vmin=0, vmax=1, **scatter_kw)
    fig.colorbar(m_scatter, ax=ax_m).set_label("Motivation to adopt")
    ax_m.set_title("Motivation")

    _draw_network_edges(ax_o, result.locations, result.graph)
    o_scatter = ax_o.scatter(x, y, c=_ownership_colours(result, 0), **scatter_kw)
    ax_o.set_title("Heat pump ownership")
    ax_o.legend(handles=[plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c, markersize=9, label=label)
                         for label, c in OWNERSHIP], loc="upper right", fontsize=8)

    for ax in (ax_m, ax_o):
        ax.set_xlabel("x")
        ax.set_ylabel("y")
    suptitle = fig.suptitle("Month 0", fontsize=14)

    def update(t):
        m_scatter.set_array(h.motivation[t])
        o_scatter.set_facecolor(_ownership_colours(result, t))
        suptitle.set_text(f"Month {t} (year {t / 12:.1f}): {100 * h.owner[t].mean():.1f}% own a heat pump")
        return m_scatter, o_scatter, suptitle

    anim = FuncAnimation(fig, update, frames=frames, blit=False)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    anim.save(out_path, writer=PillowWriter(fps=fps))
    plt.close(fig)
