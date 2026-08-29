from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from .refusals import refuse


@dataclass(frozen=True, slots=True)
class FiniteDistribution:
    mass: tuple[tuple[str, Fraction], ...]

    @classmethod
    def from_mapping(cls, values: Mapping[str, Fraction | int]) -> "FiniteDistribution":
        if not values:
            raise refuse("EMPTY_DISTRIBUTION", "distribution must contain support")
        items = tuple(sorted((key, Fraction(value)) for key, value in values.items()))
        if any(not key or value < 0 for key, value in items):
            raise refuse("INVALID_DISTRIBUTION", "keys must be nonblank and mass nonnegative")
        total = sum((value for _, value in items), Fraction(0))
        if total <= 0:
            raise refuse("ZERO_TOTAL_MASS", "distribution must have positive total mass")
        return cls(tuple((key, value / total) for key, value in items))

    def as_dict(self) -> dict[str, Fraction]:
        return dict(self.mass)

    @property
    def support(self) -> frozenset[str]:
        return frozenset(key for key, value in self.mass if value > 0)
