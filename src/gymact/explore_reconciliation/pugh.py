from __future__ import annotations

from collections.abc import Mapping


def weighted_pugh(
    scores: Mapping[str, Mapping[str, float]],
    weights: Mapping[str, float],
) -> tuple[tuple[str, float], ...]:
    if any(weight < 0 for weight in weights.values()) or not weights:
        raise ValueError("REFUSED_INVALID_PUGH_WEIGHTS")
    totals: list[tuple[str, float]] = []
    for candidate, dimensions in scores.items():
        missing = set(weights) - set(dimensions)
        if missing:
            raise ValueError("REFUSED_INCOMPLETE_PUGH_VECTOR")
        totals.append((candidate, sum(dimensions[key] * weights[key] for key in weights)))
    return tuple(sorted(totals, key=lambda item: (-item[1], item[0])))
