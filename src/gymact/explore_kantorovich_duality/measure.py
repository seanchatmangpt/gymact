from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .refusal import DualityRefusal


@dataclass(frozen=True)
class FiniteMeasure:
    mass: dict[str, Fraction]

    @classmethod
    def normalize(cls, values: dict[str, Fraction | int]) -> "FiniteMeasure":
        if not values:
            raise DualityRefusal("EMPTY_MEASURE", "support must be nonempty")
        raw = {k: Fraction(v) for k, v in values.items()}
        if any(v < 0 for v in raw.values()):
            raise DualityRefusal("NEGATIVE_MASS", "mass must be nonnegative")
        total = sum(raw.values(), Fraction(0))
        if total <= 0:
            raise DualityRefusal("ZERO_MASS", "total mass must be positive")
        return cls({k: v / total for k, v in raw.items() if v})

    @property
    def support(self) -> frozenset[str]:
        return frozenset(self.mass)
