from __future__ import annotations

from .selector import Candidate


def dominates(a: Candidate, b: Candidate) -> bool:
    no_worse = (
        a.expected_loss <= b.expected_loss
        and a.false_independent_rate <= b.false_independent_rate
        and a.information_value >= b.information_value
        and a.drift_risk <= b.drift_risk
    )
    strictly = (
        a.expected_loss < b.expected_loss
        or a.false_independent_rate < b.false_independent_rate
        or a.information_value > b.information_value
        or a.drift_risk < b.drift_risk
    )
    return no_worse and strictly


def frontier(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    survivors = [
        candidate
        for candidate in candidates
        if not any(dominates(other, candidate) for other in candidates if other is not candidate)
    ]
    return tuple(sorted(survivors, key=lambda c: c.name))
