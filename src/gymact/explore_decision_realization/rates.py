from collections.abc import Iterable
from dataclasses import dataclass

from .decision import Decision
from .errors import Refused


@dataclass(frozen=True, slots=True)
class LabeledDecision:
    decision: Decision
    actually_independent: bool


@dataclass(frozen=True, slots=True)
class DirectionalRates:
    support: int
    false_independent: float
    false_dependent: float
    defer_rate: float


def directional_rates(items: Iterable[LabeledDecision]) -> DirectionalRates:
    rows = tuple(items)
    if not rows:
        raise Refused("INSUFFICIENT_REALIZATION_SUPPORT")
    false_i = sum(x.decision is Decision.INDEPENDENT and not x.actually_independent for x in rows)
    false_d = sum(x.decision is Decision.DEPENDENT and x.actually_independent for x in rows)
    defer = sum(x.decision is Decision.DEFER for x in rows)
    n = len(rows)
    return DirectionalRates(n, false_i / n, false_d / n, defer / n)
