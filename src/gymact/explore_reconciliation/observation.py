from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from .subject import Subject

Outcome = Literal["PASS", "FAIL", "PENDING", "UNKNOWN", "UNSUPPORTED"]


@dataclass(frozen=True, slots=True)
class Observation:
    subject: Subject
    axis: str
    outcome: Outcome
    observed_at: datetime
    source: str

    def __post_init__(self) -> None:
        if not self.axis.strip() or not self.source.strip():
            raise ValueError("REFUSED_UNBOUNDED_OBSERVATION")
        if self.observed_at.tzinfo is None:
            raise ValueError("REFUSED_NAIVE_OBSERVATION_TIME")
