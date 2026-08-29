from dataclasses import dataclass
from fractions import Fraction

from .refusals import FusionRefused


@dataclass(frozen=True, slots=True)
class ErrorDistribution:
    current: Fraction
    stale: Fraction
    ambiguous: Fraction

    def __post_init__(self) -> None:
        values = (self.current, self.stale, self.ambiguous)
        if any(v < 0 for v in values) or sum(values) != 1:
            raise FusionRefused("REFUSED_INVALID_ERROR_DISTRIBUTION")

    def as_tuple(self) -> tuple[Fraction, Fraction, Fraction]:
        return self.current, self.stale, self.ambiguous
