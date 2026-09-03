from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .refusal import Refused


@dataclass(frozen=True, slots=True)
class ObservationWindow:
    since: datetime
    until: datetime

    def __post_init__(self) -> None:
        if any(
            value.tzinfo is None or value.utcoffset() is None for value in (self.since, self.until)
        ):
            raise Refused("REFUSED_NAIVE_OBSERVATION_WINDOW")
        if self.since >= self.until:
            raise Refused("REFUSED_INVALID_OBSERVATION_WINDOW")

    def contains(self, value: datetime) -> bool:
        return self.since <= value < self.until
