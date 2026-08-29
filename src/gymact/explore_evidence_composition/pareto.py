from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    lower_confidence: float
    uncertainty: float
    cost: float
    semantic_strength: int


def dominates(left: Candidate, right: Candidate) -> bool:
    no_worse = (
        left.lower_confidence >= right.lower_confidence
        and left.uncertainty <= right.uncertainty
        and left.cost <= right.cost
        and left.semantic_strength >= right.semantic_strength
    )
    strict = (
        left.lower_confidence > right.lower_confidence
        or left.uncertainty < right.uncertainty
        or left.cost < right.cost
        or left.semantic_strength > right.semantic_strength
    )
    return no_worse and strict


def frontier(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    return tuple(
        candidate
        for candidate in candidates
        if not any(dominates(other, candidate) for other in candidates if other != candidate)
    )
