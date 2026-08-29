from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from .refusal import Refused

@dataclass(frozen=True)
class Candidate:
    identity: str
    nominal: Fraction
    worst: Fraction
    radius: Fraction
    support: int
    oracle_gap: Fraction = Fraction()

class Strategy(str, Enum):
    MIN_NOMINAL = "min_nominal"
    MIN_WORST = "min_worst"
    MIN_RADIUS = "min_radius"
    MAX_SUPPORT = "max_support"
    MIN_ORACLE_GAP = "min_oracle_gap"

def select(candidates: tuple[Candidate, ...], strategy: Strategy) -> Candidate:
    if not candidates:
        raise Refused("EMPTY_CANDIDATE_SET")
    keys = {
        Strategy.MIN_NOMINAL: lambda c: (c.nominal, c.identity),
        Strategy.MIN_WORST: lambda c: (c.worst, c.identity),
        Strategy.MIN_RADIUS: lambda c: (c.radius, c.identity),
        Strategy.MAX_SUPPORT: lambda c: (-c.support, c.identity),
        Strategy.MIN_ORACLE_GAP: lambda c: (c.oracle_gap, c.identity),
    }
    return min(candidates, key=keys[strategy])
