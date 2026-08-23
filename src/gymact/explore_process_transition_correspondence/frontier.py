from __future__ import annotations

from collections import defaultdict

from .epoch import SubjectEpoch
from .identity import Refused


def current_frontier(epochs: list[SubjectEpoch]) -> SubjectEpoch:
    if not epochs:
        raise Refused("REFUSED_EMPTY_FRONTIER")
    by_generation: dict[int, set[str]] = defaultdict(set)
    by_value: dict[tuple[int, str], SubjectEpoch] = {}
    for epoch in epochs:
        by_generation[epoch.generation].add(epoch.subject.canonical)
        by_value[(epoch.generation, epoch.subject.canonical)] = epoch
    generation = max(by_generation)
    heads = by_generation[generation]
    if len(heads) != 1:
        raise Refused("REFUSED_DIVERGENT_CURRENT_FRONTIER")
    canonical = next(iter(heads))
    return by_value[(generation, canonical)]
