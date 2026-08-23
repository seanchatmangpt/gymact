from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from .refusal import Refused


class ObligationState(StrEnum):
    PASS = "PASS"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"
    REFUSED = "REFUSED"
    BLOCKED = "BLOCKED"
    FAIL = "FAIL"


WEIGHT = {
    ObligationState.PASS: Fraction(0),
    ObligationState.UNSUPPORTED: Fraction(1, 5),
    ObligationState.UNKNOWN: Fraction(2, 5),
    ObligationState.REFUSED: Fraction(3, 5),
    ObligationState.BLOCKED: Fraction(4, 5),
    ObligationState.FAIL: Fraction(1),
}


@dataclass(frozen=True, slots=True)
class Obligation:
    key: str
    state: ObligationState
    source: str

    def __post_init__(self) -> None:
        if not self.key.strip() or not self.source.strip():
            raise Refused("INVALID_OBLIGATION", self.key)

    @property
    def debt(self) -> Fraction:
        return WEIGHT[self.state]
