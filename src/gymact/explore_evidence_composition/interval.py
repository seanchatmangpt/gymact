from __future__ import annotations

from dataclasses import dataclass

from .refusal import RefusalCode, Refused


@dataclass(frozen=True, slots=True, order=True)
class Interval:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.lower <= self.upper <= 1.0):
            raise Refused(RefusalCode.INVALID_INTERVAL, f"invalid [{self.lower}, {self.upper}]")

    def meet(self, other: Interval) -> Interval:
        """Conservative conjunction without assuming independence (Frechet lower bound)."""
        return Interval(max(0.0, self.lower + other.lower - 1.0), min(self.upper, other.upper))

    def independent_product(self, other: Interval) -> Interval:
        """Conjunction when an admitted independence witness exists."""
        return Interval(self.lower * other.lower, self.upper * other.upper)

    @property
    def width(self) -> float:
        return self.upper - self.lower
