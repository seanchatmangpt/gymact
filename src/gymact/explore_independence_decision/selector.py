from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction


class Strategy(StrEnum):
    MIN_EXPECTED_LOSS = "MIN_EXPECTED_LOSS"
    MIN_FALSE_INDEPENDENT = "MIN_FALSE_INDEPENDENT"
    MAX_INFORMATION_VALUE = "MAX_INFORMATION_VALUE"
    ROBUST_DEFER = "ROBUST_DEFER"


@dataclass(frozen=True)
class Candidate:
    name: str
    expected_loss: Fraction
    false_independent_rate: Fraction
    information_value: Fraction
    drift_risk: Fraction


def select(candidates: tuple[Candidate, ...], strategy: Strategy) -> Candidate:
    if not candidates:
        raise ValueError("no candidates")
    if strategy is Strategy.MIN_EXPECTED_LOSS:
        return min(candidates, key=lambda c: (c.expected_loss, c.name))
    if strategy is Strategy.MIN_FALSE_INDEPENDENT:
        return min(candidates, key=lambda c: (c.false_independent_rate, c.expected_loss, c.name))
    if strategy is Strategy.MAX_INFORMATION_VALUE:
        return max(candidates, key=lambda c: (c.information_value, -c.expected_loss, c.name))
    return min(candidates, key=lambda c: (c.drift_risk, c.false_independent_rate, c.name))
