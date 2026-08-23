from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction

from .bound import RobustnessBound
from .refusal import REFUSED_INVALID_CASE, Refused
from .subject import Subject


@dataclass(frozen=True, slots=True)
class BoundCase:
    subject: Subject
    bound: RobustnessBound
    truth: Fraction
    observed_at: datetime
    case_id: str

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise Refused(REFUSED_INVALID_CASE, "empty case id")
        if self.observed_at.tzinfo is None:
            raise Refused(REFUSED_INVALID_CASE, "naive time")
        if self.observed_at > datetime.now(UTC):
            raise Refused(REFUSED_INVALID_CASE, "future evidence")

    @property
    def covered(self) -> bool:
        return self.bound.lower <= self.truth <= self.bound.upper
