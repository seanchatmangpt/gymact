from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ObservationWindow:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("REFUSED_NAIVE_OBSERVATION_WINDOW")
        if self.start >= self.end:
            raise ValueError("REFUSED_INVALID_OBSERVATION_WINDOW")

    def contains(self, observed_at: datetime) -> bool:
        if observed_at.tzinfo is None:
            raise ValueError("REFUSED_NAIVE_OBSERVATION_TIME")
        return self.start <= observed_at < self.end
