from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .obligation import Obligation, ObligationState


@dataclass(frozen=True, slots=True)
class Census:
    total: int
    passed: int
    failed: int
    unknown: int
    refused: int

    @property
    def closure(self) -> Fraction:
        return Fraction(self.passed, self.total) if self.total else Fraction(0, 1)


def census(items: list[Obligation]) -> Census:
    by_key = {item.key: item for item in items}
    values = tuple(by_key[key].state for key in sorted(by_key))
    return Census(
        total=len(values),
        passed=values.count(ObligationState.PASS),
        failed=values.count(ObligationState.FAIL),
        unknown=values.count(ObligationState.UNKNOWN),
        refused=values.count(ObligationState.REFUSED),
    )
