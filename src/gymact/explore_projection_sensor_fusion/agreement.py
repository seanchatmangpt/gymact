from dataclasses import dataclass
from fractions import Fraction

from .refusals import FusionRefused


@dataclass(frozen=True, slots=True)
class Agreement:
    shared: int
    matching: int

    def __post_init__(self) -> None:
        if self.shared < 0 or self.matching < 0 or self.matching > self.shared:
            raise FusionRefused("REFUSED_INVALID_AGREEMENT")

    @property
    def ratio(self) -> Fraction:
        return Fraction(self.matching, self.shared) if self.shared else Fraction(0, 1)
