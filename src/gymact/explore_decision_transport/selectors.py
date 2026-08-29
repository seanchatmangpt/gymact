from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction


class Strategy(StrEnum):
    MIN_TRANSPORT_RISK = "MIN_TRANSPORT_RISK"
    MAX_SUPPORT = "MAX_SUPPORT"
    MIN_SHIFT = "MIN_SHIFT"
    MAX_ESS = "MAX_ESS"


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    risk: Fraction
    support: Fraction
    shift: Fraction
    ess: Fraction


def select(candidates: list[Candidate], strategy: Strategy) -> Candidate:
    if strategy is Strategy.MIN_TRANSPORT_RISK:
        return min(candidates, key=lambda c: (c.risk, c.name))
    if strategy is Strategy.MAX_SUPPORT:
        return max(candidates, key=lambda c: (c.support, c.name))
    if strategy is Strategy.MIN_SHIFT:
        return min(candidates, key=lambda c: (c.shift, c.name))
    return max(candidates, key=lambda c: (c.ess, c.name))
