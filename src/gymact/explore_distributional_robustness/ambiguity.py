from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from enum import StrEnum

from .distribution import FiniteDistribution
from .divergence import total_variation
from .refusals import refuse


class AmbiguityKind(StrEnum):
    TV = "TV"
    WASSERSTEIN = "WASSERSTEIN"
    CHI_SQUARE = "CHI_SQUARE"


@dataclass(frozen=True, slots=True)
class AmbiguitySet:
    center: FiniteDistribution
    kind: AmbiguityKind
    radius: Fraction

    def __post_init__(self) -> None:
        if self.radius < 0:
            raise refuse("INVALID_RADIUS", "ambiguity radius must be nonnegative")

    def admits_tv(self, candidate: FiniteDistribution) -> bool:
        if self.kind is not AmbiguityKind.TV:
            raise refuse("WRONG_AMBIGUITY_METRIC", "TV membership requested for a different ambiguity kind")
        return total_variation(self.center, candidate) <= self.radius
