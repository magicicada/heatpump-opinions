"""Loading and access for the simulation's settings.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class Settings:
    """Thin wrapper around the parsed settings dict with dotted-path access."""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    @classmethod
    def load(cls, path: str | Path) -> "Settings":
        with open(path) as f:
            return cls(yaml.safe_load(f))

    def get(self, dotted_key: str, default: Any = None) -> Any:
        node = self._data
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @property
    def raw(self) -> dict[str, Any]:
        return self._data
