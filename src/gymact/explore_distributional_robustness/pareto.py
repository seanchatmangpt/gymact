from __future__ import annotations

from .selectors import Candidate


def dominates(left: Candidate, right: Candidate) -> bool:
    no_worse = (
        left.nominal_risk <= right.nominal_risk
        and left.worst_risk <= right.worst_risk
        and left.radius <= right.radius
        and left.support >= right.support
    )
    strictly_better = (
        left.nominal_risk < right.nominal_risk
        or left.worst_risk < right.worst_risk
        or left.radius < right.radius
        or left.support > right.support
    )
    return no_worse and strictly_better


def frontier(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    return tuple(
        candidate
        for candidate in candidates
        if not any(dominates(other, candidate) for other in candidates if other != candidate)
    )
