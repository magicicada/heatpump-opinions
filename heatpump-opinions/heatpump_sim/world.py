"""The world file format.

A "world" is the synthetic population the simulation runs on: where each
household sits in space and what it is like. Generating a world and
simulating on it are deliberately separate stages, and this module is the
only contract between them — `generate_world.py` writes a world file, the
simulation reads one, and neither needs to know how the other works.

Format: CSV, one row per household, with a leading block of `#` comment
lines carrying provenance metadata (which generator settings and seed
produced this file). Readers skip the comment block.

Columns fall into two groups.

CORE — required. The simulation refuses to load a file without these:
    id              unique integer household identifier
    x, y            position in the geographic space (floats)
    characteristic  the demographic/economic capability number, in [0, 1]

DESCRIPTIVE — optional. Carried through to the results untouched and
available for analysis, but the core dynamics never read them. These are
the attributes the `characteristic` was built from, kept so a run can be
broken down by tenure or building type after the fact, and so the
provenance of the number is not lost:
    lsoa_id         identifier of the LSOA-like cell the household is in
    lsoa_archetype  name of the archetype that cell was drawn from
    income_decile   1-10
    tenure          owner_occupied | private_rented | social_rented
    building_type   detached | semi_detached | terraced | flat

Any further columns are preserved as descriptive attributes too, so the
format can carry real survey fields later without a code change here.

Keeping `characteristic` in the file — rather than the simulation deriving
it from tenure/income at load time — is what makes the stages independent:
how the number is composed is a world-generation question, and the
simulation only needs the number itself.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np

FORMAT_VERSION = 1
CORE_COLUMNS = ("id", "x", "y", "characteristic")
DESCRIPTIVE_COLUMNS = (
    "lsoa_id",
    "lsoa_archetype",
    "income_decile",
    "tenure",
    "building_type",
)


@dataclass
class World:
    """A loaded world file."""

    ids: np.ndarray                              # (n,) int
    locations: np.ndarray                        # (n, 2) float
    characteristic: np.ndarray                   # (n,) float in [0, 1]
    attributes: dict[str, np.ndarray] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.ids)


class WorldFormatError(ValueError):
    """Raised when a world file is malformed. Carries enough detail to find
    the offending row, because a silently misread population would produce
    plausible-looking but meaningless results."""


def _strip_comments(lines: Iterable[str]) -> tuple[list[str], dict[str, str]]:
    """Split a `#`-commented header off the CSV body, parsing `# key: value`
    lines into a metadata dict."""
    body, metadata = [], {}
    for line in lines:
        if line.lstrip().startswith("#"):
            comment = line.lstrip().lstrip("#").strip()
            if ":" in comment:
                key, _, value = comment.partition(":")
                metadata[key.strip()] = value.strip()
        else:
            body.append(line)
    return body, metadata


def read_world(path: str | Path) -> World:
    """Read and validate a world file."""
    path = Path(path)
    if not path.exists():
        raise WorldFormatError(f"World file not found: {path}")

    with open(path, newline="") as f:
        body, metadata = _strip_comments(f.readlines())

    if not body:
        raise WorldFormatError(f"{path}: file contains no data rows")

    reader = csv.DictReader(body)
    if reader.fieldnames is None:
        raise WorldFormatError(f"{path}: missing header row")

    fieldnames = [name.strip() for name in reader.fieldnames]
    missing = [c for c in CORE_COLUMNS if c not in fieldnames]
    if missing:
        raise WorldFormatError(
            f"{path}: missing required column(s) {missing}. "
            f"Required: {list(CORE_COLUMNS)}; found: {fieldnames}"
        )

    extra_columns = [c for c in fieldnames if c not in CORE_COLUMNS]

    ids: list[int] = []
    xs: list[float] = []
    ys: list[float] = []
    characteristic: list[float] = []
    attributes: dict[str, list[str]] = {c: [] for c in extra_columns}

    for lineno, row in enumerate(reader, start=2):  # header is line 1
        def _number(column: str, cast):
            raw = (row.get(column) or "").strip()
            if raw == "":
                raise WorldFormatError(f"{path}:{lineno}: empty value for {column!r}")
            try:
                return cast(raw)
            except ValueError:
                raise WorldFormatError(
                    f"{path}:{lineno}: could not read {column!r} value {raw!r} as {cast.__name__}"
                ) from None

        ids.append(_number("id", int))
        xs.append(_number("x", float))
        ys.append(_number("y", float))
        characteristic.append(_number("characteristic", float))

        for column in extra_columns:
            attributes[column].append((row.get(column) or "").strip())

    world = World(
        ids=np.array(ids, dtype=int),
        locations=np.column_stack([xs, ys]).astype(float),
        characteristic=np.array(characteristic, dtype=float),
        attributes={c: np.array(v) for c, v in attributes.items()},
        metadata=metadata,
    )
    _validate(world, path)
    return world


def _validate(world: World, path: Path) -> None:
    if world.n == 0:
        raise WorldFormatError(f"{path}: no households found")

    if len(np.unique(world.ids)) != world.n:
        duplicates = [int(i) for i in np.unique(world.ids) if (world.ids == i).sum() > 1]
        raise WorldFormatError(f"{path}: duplicate household id(s) {duplicates[:10]}")

    if not np.isfinite(world.locations).all():
        bad = np.where(~np.isfinite(world.locations).all(axis=1))[0]
        raise WorldFormatError(f"{path}: non-finite coordinates at row index/indices {bad[:10].tolist()}")

    out_of_range = np.where((world.characteristic < 0.0) | (world.characteristic > 1.0))[0]
    if len(out_of_range):
        raise WorldFormatError(
            f"{path}: characteristic must lie in [0, 1]; "
            f"{len(out_of_range)} row(s) outside, first at row index {int(out_of_range[0])} "
            f"with value {world.characteristic[out_of_range[0]]}"
        )


def write_world(
    path: str | Path,
    ids: np.ndarray,
    locations: np.ndarray,
    characteristic: np.ndarray,
    attributes: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write a world file, with a `# key: value` provenance header."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    attributes = attributes or {}
    metadata = metadata or {}

    n = len(ids)
    for name, values in attributes.items():
        if len(values) != n:
            raise ValueError(f"attribute {name!r} has {len(values)} values, expected {n}")

    # Descriptive columns first in their canonical order, then anything else.
    ordered_extra = [c for c in DESCRIPTIVE_COLUMNS if c in attributes]
    ordered_extra += [c for c in attributes if c not in DESCRIPTIVE_COLUMNS]
    columns = list(CORE_COLUMNS) + ordered_extra

    with open(path, "w", newline="") as f:
        f.write(f"# heatpump-opinions world file, format version {FORMAT_VERSION}\n")
        f.write(f"# households: {n}\n")
        for key, value in metadata.items():
            f.write(f"# {key}: {value}\n")

        writer = csv.writer(f)
        writer.writerow(columns)
        for i in range(n):
            row = [
                int(ids[i]),
                f"{locations[i, 0]:.6f}",
                f"{locations[i, 1]:.6f}",
                f"{characteristic[i]:.6f}",
            ]
            row += [attributes[c][i] for c in ordered_extra]
            writer.writerow(row)
