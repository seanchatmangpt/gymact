from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .refusal import DualityRefusal


@dataclass(frozen=True)
class GroundMetric:
    cost: dict[tuple[str, str], Fraction]

    @classmethod
    def admit(cls, support: set[str], cost: dict[tuple[str, str], Fraction | int]) -> "GroundMetric":
        c = {k: Fraction(v) for k, v in cost.items()}
        for x in support:
            if c.get((x, x), Fraction(0)) != 0:
                raise DualityRefusal("NONZERO_DIAGONAL", x)
            for y in support:
                if (x, y) not in c and x != y:
                    raise DualityRefusal("MISSING_GROUND_COST", f"{x}->{y}")
                if c.get((x, y), Fraction(0)) < 0:
                    raise DualityRefusal("NEGATIVE_GROUND_COST", f"{x}->{y}")
                if c.get((x, y), Fraction(0)) != c.get((y, x), Fraction(0)):
                    raise DualityRefusal("ASYMMETRIC_GROUND_COST", f"{x}<->{y}")
        for x in support:
            for y in support:
                for z in support:
                    if c.get((x, z), Fraction(0)) > c.get((x, y), Fraction(0)) + c.get((y, z), Fraction(0)):
                        raise DualityRefusal("TRIANGLE_VIOLATION", f"{x},{y},{z}")
        return cls(c)

    def __call__(self, x: str, y: str) -> Fraction:
        return self.cost.get((x, y), Fraction(0))
