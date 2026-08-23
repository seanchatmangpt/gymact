from dataclasses import dataclass
from enum import StrEnum
from collections.abc import Iterable

from .decision import Decision
from .errors import Refused

class Strategy(StrEnum):
    MIN_REALIZED_RISK = "MIN_REALIZED_RISK"
    MIN_FALSE_INDEPENDENT = "MIN_FALSE_INDEPENDENT"
    MAX_REALIZED_INFORMATION = "MAX_REALIZED_INFORMATION"
    ROBUST_DEFER = "ROBUST_DEFER"

@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    decision: Decision
    realized_risk: float
    false_independent_rate: float
    realized_information: float
    drift_risk: float


def select(candidates: Iterable[Candidate], strategy: Strategy) -> Candidate:
    rows = tuple(candidates)
    if not rows:
        raise Refused("NO_DECISION_CANDIDATE")
    if strategy is Strategy.MIN_REALIZED_RISK:
        return min(rows, key=lambda c: (c.realized_risk, c.drift_risk, c.name))
    if strategy is Strategy.MIN_FALSE_INDEPENDENT:
        return min(rows, key=lambda c: (c.false_independent_rate, c.realized_risk, c.name))
    if strategy is Strategy.MAX_REALIZED_INFORMATION:
        return max(rows, key=lambda c: (c.realized_information, -c.realized_risk, c.name))
    deferred = tuple(row for row in rows if row.decision is Decision.DEFER)
    return min(deferred or rows, key=lambda c: (c.drift_risk, c.realized_risk, c.name))
