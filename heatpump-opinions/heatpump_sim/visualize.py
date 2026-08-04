"""Animated visualisations of the simulation: opinion evolution (continuous
colour scale) and heat pump adoption (binary colour) over the geographic
layout of households."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter

from .simulate import SimulationResult


def _draw_network_edges(ax, locations: np.ndarray, graph: nx.Graph) -> None:
    for u, v in graph.edges():
        x = [locations[u, 0], locations[v, 0]]
        y = [locations[u, 1], locations[v, 1]]
        ax.plot(x, y, color="grey", linewidth=0.4, alpha=0.25, zorder=1)


def animate_opinions(result: SimulationResult, out_path: str | Path, fps: int = 8) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    _draw_network_edges(ax, result.locations, result.graph)

    scatter = ax.scatter(
        result.locations[:, 0],
        result.locations[:, 1],
        c=result.opinion_history[0],
        cmap="RdYlGn",
        vmin=0,
        vmax=1,
        s=60,
        edgecolors="black",
        linewidths=0.4,
        zorder=2,
    )
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Opinion of heat pumps")
    title = ax.set_title("Opinion evolution — t=0")
    ax.set_xlabel("x")
    ax.set_ylabel("y")

    def update(frame):
        scatter.set_array(result.opinion_history[frame])
        title.set_text(f"Opinion evolution — t={frame}")
        return scatter, title

    anim = FuncAnimation(fig, update, frames=len(result.opinion_history), blit=False)
    anim.save(out_path, writer=PillowWriter(fps=fps))
    plt.close(fig)


def animate_heatpumps(result: SimulationResult, out_path: str | Path, fps: int = 8) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    _draw_network_edges(ax, result.locations, result.graph)

    colors = np.where(result.heatpump_history[0], "#1f77b4", "#d3d3d3")
    scatter = ax.scatter(
        result.locations[:, 0],
        result.locations[:, 1],
        c=colors,
        s=60,
        edgecolors="black",
        linewidths=0.4,
        zorder=2,
    )
    title = ax.set_title("Heat pump adoption — t=0")
    ax.set_xlabel("x")
    ax.set_ylabel("y")

    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#1f77b4", markersize=9, label="Has heat pump"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#d3d3d3", markersize=9, label="No heat pump"),
    ]
    ax.legend(handles=handles, loc="upper right")

    def update(frame):
        colors = np.where(result.heatpump_history[frame], "#1f77b4", "#d3d3d3")
        scatter.set_facecolor(colors)
        title.set_text(f"Heat pump adoption — t={frame}")
        return scatter, title

    anim = FuncAnimation(fig, update, frames=len(result.heatpump_history), blit=False)
    anim.save(out_path, writer=PillowWriter(fps=fps))
    plt.close(fig)


def animate_combined(result: SimulationResult, out_path: str | Path, fps: int = 8) -> None:
    """Opinion and heat-pump-adoption panels side by side, stepping through
    the same timestep together."""
    fig, (ax_op, ax_hp) = plt.subplots(1, 2, figsize=(13, 6))

    _draw_network_edges(ax_op, result.locations, result.graph)
    op_scatter = ax_op.scatter(
        result.locations[:, 0],
        result.locations[:, 1],
        c=result.opinion_history[0],
        cmap="RdYlGn",
        vmin=0,
        vmax=1,
        s=60,
        edgecolors="black",
        linewidths=0.4,
        zorder=2,
    )
    cbar = fig.colorbar(op_scatter, ax=ax_op)
    cbar.set_label("Opinion of heat pumps")
    op_title = ax_op.set_title("Opinion")
    ax_op.set_xlabel("x")
    ax_op.set_ylabel("y")

    _draw_network_edges(ax_hp, result.locations, result.graph)
    hp_colors = np.where(result.heatpump_history[0], "#1f77b4", "#d3d3d3")
    hp_scatter = ax_hp.scatter(
        result.locations[:, 0],
        result.locations[:, 1],
        c=hp_colors,
        s=60,
        edgecolors="black",
        linewidths=0.4,
        zorder=2,
    )
    hp_title = ax_hp.set_title("Heat pump adoption")
    ax_hp.set_xlabel("x")
    ax_hp.set_ylabel("y")
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#1f77b4", markersize=9, label="Has heat pump"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#d3d3d3", markersize=9, label="No heat pump"),
    ]
    ax_hp.legend(handles=handles, loc="upper right")

    suptitle = fig.suptitle("t=0", fontsize=14)

    def update(frame):
        op_scatter.set_array(result.opinion_history[frame])
        hp_scatter.set_facecolor(np.where(result.heatpump_history[frame], "#1f77b4", "#d3d3d3"))
        suptitle.set_text(f"t={frame}")
        return op_scatter, hp_scatter, suptitle

    anim = FuncAnimation(fig, update, frames=len(result.opinion_history), blit=False)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    anim.save(out_path, writer=PillowWriter(fps=fps))
    plt.close(fig)
