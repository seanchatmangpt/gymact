from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from .ground import GroundMetric
from .kantorovich import wasserstein1
from .measure import FiniteMeasure, common_support, q
from .refusal import Refused

class Kind(str, Enum):
    WASSERSTEIN1 = "wasserstein1"
    CHI_SQUARE = "chi_square"
    TOTAL_VARIATION = "total_variation"

def total_variation(a: FiniteMeasure, b: FiniteMeasure) -> Fraction:
    return sum((abs(a.probability(k) - b.probability(k)) for k in common_support(a, b)), Fraction()) / 2

def chi_square(candidate: FiniteMeasure, center: FiniteMeasure) -> Fraction:
    value = Fraction()
    for k in common_support(candidate, center):
        p, qv = candidate.probability(k), center.probability(k)
        if p and not qv:
            raise Refused("CHI_SQUARE_POSITIVITY", k)
        if qv:
            value += (p - qv) ** 2 / qv
    return value

@dataclass(frozen=True)
class AmbiguitySet:
    center: FiniteMeasure
    kind: Kind
    radius: Fraction
    metric: GroundMetric | None = None

    @classmethod
    def create(cls, center: FiniteMeasure, kind: Kind, radius: int | str | Fraction, metric: GroundMetric | None = None) -> "AmbiguitySet":
        r = q(radius)
        if r < 0:
            raise Refused("NEGATIVE_AMBIGUITY_RADIUS")
        if kind is Kind.WASSERSTEIN1 and metric is None:
            raise Refused("WASSERSTEIN_REQUIRES_GROUND_METRIC")
        return cls(center, kind, r, metric)

    def distance(self, candidate: FiniteMeasure) -> Fraction:
        if self.kind is Kind.WASSERSTEIN1:
            assert self.metric is not None
            return wasserstein1(self.center, candidate, self.metric).cost
        if self.kind is Kind.CHI_SQUARE:
            return chi_square(candidate, self.center)
        return total_variation(candidate, self.center)

    def contains(self, candidate: FiniteMeasure) -> bool:
        return self.distance(candidate) <= self.radius
