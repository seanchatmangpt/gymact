from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from .causality import causal_profile
from .refusal import Refused
from .replica import ReplicaProjection
from .universe import ReplicaUniverse


class SelectorKind(StrEnum):
    STRICT_MAJORITY_CURRENTNESS = "STRICT_MAJORITY_CURRENTNESS"
    MAX_COVERAGE_FRESHNESS = "MAX_COVERAGE_FRESHNESS"
    CAUSAL_MAXIMA_CONSERVATIVE = "CAUSAL_MAXIMA_CONSERVATIVE"
    MINIMAX_AMBIGUITY = "MINIMAX_AMBIGUITY"


@dataclass(frozen=True, slots=True)
class Selection:
    selector: SelectorKind
    generation: int
    projection_digest: str
    replica_ids: tuple[str, ...]
    coverage: Fraction


def _clusters(
    observations: tuple[ReplicaProjection, ...],
) -> dict[tuple[int, str], tuple[ReplicaProjection, ...]]:
    groups: dict[tuple[int, str], list[ReplicaProjection]] = {}
    for item in observations:
        groups.setdefault((item.generation, item.projection_digest), []).append(item)
    return {key: tuple(value) for key, value in groups.items()}


def select(
    selector: SelectorKind,
    observations: tuple[ReplicaProjection, ...],
    universe: ReplicaUniverse,
) -> Selection:
    if not observations:
        raise Refused("REFUSED_NO_PROJECTION_EVIDENCE")
    groups = _clusters(observations)
    if selector is SelectorKind.STRICT_MAJORITY_CURRENTNESS:
        highest = max(item.generation for item in observations)
        candidates = [
            (key, members)
            for key, members in groups.items()
            if key[0] == highest and len(members) >= universe.quorum_size
        ]
    elif selector is SelectorKind.MAX_COVERAGE_FRESHNESS:
        candidates = sorted(
            groups.items(),
            key=lambda item: (len(item[1]), item[0][0], item[0][1]),
            reverse=True,
        )[:1]
    elif selector is SelectorKind.CAUSAL_MAXIMA_CONSERVATIVE:
        maxima = set(causal_profile(observations).maximal_replica_ids)
        candidates = [
            (key, tuple(member for member in members if member.replica_id in maxima))
            for key, members in groups.items()
        ]
        candidates = [(key, members) for key, members in candidates if members]
        if len({key[1] for key, _ in candidates}) != 1:
            raise Refused("REFUSED_CAUSAL_MAXIMA_AMBIGUOUS")
    else:
        conflict = {key: len(observations) - len(members) for key, members in groups.items()}
        best = min(conflict.values())
        candidates = [(key, members) for key, members in groups.items() if conflict[key] == best]
        max_generation = max(key[0] for key, _ in candidates)
        candidates = [(key, members) for key, members in candidates if key[0] == max_generation]
    if len(candidates) != 1:
        raise Refused("REFUSED_AMBIGUOUS_PROJECTION_SELECTION")
    (generation, digest), members = candidates[0]
    ids = tuple(sorted(item.replica_id for item in members))
    return Selection(selector, generation, digest, ids, universe.coverage(set(ids)))
