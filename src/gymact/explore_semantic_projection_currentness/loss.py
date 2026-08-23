from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class LossVector:
    identity: Fraction = Fraction(0)
    constraints: Fraction = Fraction(0)
    unit: Fraction = Fraction(0)
    time: Fraction = Fraction(0)
    ordering: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        if any(x < 0 for x in self.components):
            raise ValueError("REFUSED_NEGATIVE_INFORMATION_LOSS")

    @property
    def components(self) -> tuple[Fraction, ...]:
        return (self.identity, self.constraints, self.unit, self.time, self.ordering)

    @property
    def total(self) -> Fraction:
        return sum(self.components, Fraction(0))

    @property
    def lossless(self) -> bool:
        return self.total == 0

    def __add__(self, other: LossVector) -> LossVector:
        return LossVector(*(a + b for a, b in zip(self.components, other.components, strict=True)))
