from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    risk: Fraction
    support: Fraction
    shift: Fraction
    ess: Fraction


def select(candidates: tuple[Candidate, ...], strategy: str) -> Candidate:
    if not candidates:
        raise ValueError("no candidates")
    keys = {
        "MIN_RISK": lambda c: (c.risk, -c.support, c.name),
        "MAX_SUPPORT": lambda c: (-c.support, c.risk, c.name),
        "MIN_SHIFT": lambda c: (c.shift, c.risk, c.name),
        "MAX_ESS": lambda c: (-c.ess, c.risk, c.name),
        "MINIMAX": lambda c: (max(c.risk, c.shift, 1 - c.support), -c.ess, c.name),
    }
    if strategy not in keys:
        raise ValueError(f"unknown strategy: {strategy}")
    return min(candidates, key=keys[strategy])
