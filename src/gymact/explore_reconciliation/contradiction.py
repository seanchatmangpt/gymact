from __future__ import annotations

from collections import defaultdict

from .observation import Observation


def contradictions(observations: tuple[Observation, ...]) -> dict[str, frozenset[str]]:
    values: dict[str, set[str]] = defaultdict(set)
    for observation in observations:
        values[observation.axis].add(observation.outcome)
    return {
        axis: frozenset(outcomes) for axis, outcomes in sorted(values.items()) if len(outcomes) > 1
    }
