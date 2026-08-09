from __future__ import annotations

from copy import deepcopy
from typing import Any

from .capabilities import CLOUDS

DEFAULT_GLOBAL_TOPOLOGY: dict[str, dict[str, tuple[str, ...]]] = {
    cloud: {
        "scopes": ("prod", "shared", "security"),
        "regions": (
            "us-east",
            "us-west",
            "eu-west",
            "eu-central",
            "asia-east",
            "asia-southeast",
        ),
    }
    for cloud in CLOUDS
}


def normalize_topology(value: object | None) -> dict[str, dict[str, list[str]]]:
    source = DEFAULT_GLOBAL_TOPOLOGY if value is None else value
    if not isinstance(source, dict):
        raise TypeError("config.topology must be an object")

    result: dict[str, dict[str, list[str]]] = {}
    for cloud in CLOUDS:
        raw_cloud = source.get(cloud)
        if not isinstance(raw_cloud, dict):
            raise ValueError(f"topology.{cloud} must be an object")
        result[cloud] = {
            "scopes": _nonempty_strings(raw_cloud.get("scopes"), f"topology.{cloud}.scopes"),
            "regions": _nonempty_strings(
                raw_cloud.get("regions"), f"topology.{cloud}.regions"
            ),
        }
    return deepcopy(result)


def _nonempty_strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{label} must be a non-empty array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label} entries must be non-empty strings")
        normalized = item.strip()
        if normalized not in result:
            result.append(normalized)
    return result
