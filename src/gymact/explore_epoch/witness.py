from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .identity import Subject


class WitnessKind(str, Enum):
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISCHARGED = "DISCHARGED"
    RECOVERED = "RECOVERED"


@dataclass(frozen=True)
class Witness:
    consumer: Subject
    generation: int
    event_id: str
    kind: WitnessKind
    sequence: int
    observed_at: datetime
    parent_sequence: int | None = None

    def __post_init__(self) -> None:
        if self.generation < 0 or self.sequence < 0:
            raise ValueError("REFUSED_INVALID_WITNESS_COUNTER")
        if self.observed_at.tzinfo is None:
            raise ValueError("REFUSED_NAIVE_WITNESS_TIME")
