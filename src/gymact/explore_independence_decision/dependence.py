from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .errors import require


@dataclass(frozen=True)
class DependenceEvidence:
    ancestry_overlap: Fraction
    phi_abs: Fraction
    mutual_information: Fraction
    support: int

    def __post_init__(self) -> None:
        require(0 <= self.ancestry_overlap <= 1, "INVALID_ANCESTRY_OVERLAP")
        require(0 <= self.phi_abs <= 1, "INVALID_PHI")
        require(self.mutual_information >= 0, "INVALID_MUTUAL_INFORMATION")
        require(self.support >= 0, "INVALID_SUPPORT")

    @property
    def structurally_independent(self) -> bool:
        return self.ancestry_overlap == 0

    @property
    def empirically_independent(self) -> bool:
        return self.support > 0 and self.phi_abs == 0 and self.mutual_information == 0

    @property
    def independence_admissible(self) -> bool:
        return self.structurally_independent and self.empirically_independent
