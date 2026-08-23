from __future__ import annotations

from dataclasses import replace

from .observation import Observation


def inject_failure(observation: Observation, *, axis: str | None = None) -> Observation:
    if axis is not None and observation.axis != axis:
        return observation
    return replace(observation, outcome="FAIL", source=f"failure:{observation.source}")
