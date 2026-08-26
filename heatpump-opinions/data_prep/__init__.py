"""Data collection and preparation for the real-geography model.

Kept separate from `heatpump_sim` so the simulation itself has no dependency on
the data pipeline: the pipeline's job is to emit a household CSV that the model
reads, and nothing more.
"""
