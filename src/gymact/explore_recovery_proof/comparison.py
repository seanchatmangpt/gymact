from __future__ import annotations

from dataclasses import dataclass

from .strategies import RecoveryProtocol


@dataclass(frozen=True, slots=True)
class Score:
    protocol: RecoveryProtocol
    safety: int
    reuse: int
    requalification_cost: int


SCORES = {
    RecoveryProtocol.CAS_RESELECT: Score(RecoveryProtocol.CAS_RESELECT, 3, 1, 2),
    RecoveryProtocol.VALIDATE_REBIND: Score(RecoveryProtocol.VALIDATE_REBIND, 2, 3, 1),
    RecoveryProtocol.REQUALIFY_ONLY: Score(RecoveryProtocol.REQUALIFY_ONLY, 3, 0, 3),
}


def dominates(left: Score, right: Score) -> bool:
    left_vector = (left.safety, left.reuse, -left.requalification_cost)
    right_vector = (right.safety, right.reuse, -right.requalification_cost)
    return all(
        lhs >= rhs for lhs, rhs in zip(left_vector, right_vector, strict=True)
    ) and any(lhs > rhs for lhs, rhs in zip(left_vector, right_vector, strict=True))


def pareto(scores: tuple[Score, ...] = tuple(SCORES.values())) -> tuple[Score, ...]:
    return tuple(
        score
        for score in scores
        if not any(dominates(other, score) for other in scores if other != score)
    )
