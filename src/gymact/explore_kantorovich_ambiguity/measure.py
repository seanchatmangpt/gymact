from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from .refusal import Refused

def q(value: int | str | Fraction) -> Fraction:
    return value if isinstance(value, Fraction) else Fraction(value)

@dataclass(frozen=True)
class FiniteMeasure:
    mass: tuple[tuple[str, Fraction], ...]

    @classmethod
    def from_mapping(cls, values: Mapping[str, int | str | Fraction]) -> "FiniteMeasure":
        if not values:
            raise Refused("EMPTY_MEASURE")
        pairs = tuple(sorted((str(k), q(v)) for k, v in values.items()))
        if any(v < 0 for _, v in pairs):
            raise Refused("NEGATIVE_MASS")
        total = sum((v for _, v in pairs), Fraction())
        if total <= 0:
            raise Refused("ZERO_TOTAL_MASS")
        return cls(tuple((k, v / total) for k, v in pairs if v))

    @property
    def support(self) -> tuple[str, ...]:
        return tuple(k for k, _ in self.mass)

    def probability(self, key: str) -> Fraction:
        return dict(self.mass).get(key, Fraction())

    def expectation(self, loss: Mapping[str, int | str | Fraction]) -> Fraction:
        missing = set(self.support) - set(loss)
        if missing:
            raise Refused("MISSING_LOSS", ",".join(sorted(missing)))
        return sum((p * q(loss[k]) for k, p in self.mass), Fraction())

    def digest_tuple(self) -> tuple[tuple[str, str], ...]:
        return tuple((k, f"{v.numerator}/{v.denominator}") for k, v in self.mass)

def common_support(*measures: FiniteMeasure) -> tuple[str, ...]:
    return tuple(sorted(set().union(*(m.support for m in measures))))
