from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from .refusal import REFUSED_INVALID_BOUND, REFUSED_INVALID_GAMMA, Refused

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class RobustnessBound:
    lower: Fraction
    upper: Fraction
    gamma: Fraction
    estimator: str
    model_digest: str

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise Refused(REFUSED_INVALID_BOUND, "lower exceeds upper")
        if self.gamma < 1:
            raise Refused(REFUSED_INVALID_GAMMA, str(self.gamma))
        if not self.estimator.strip() or not _HEX64.fullmatch(self.model_digest):
            raise Refused(REFUSED_INVALID_BOUND, "missing estimator or model identity")

    @property
    def width(self) -> Fraction:
        return self.upper - self.lower

    @property
    def midpoint(self) -> Fraction:
        return (self.lower + self.upper) / 2
