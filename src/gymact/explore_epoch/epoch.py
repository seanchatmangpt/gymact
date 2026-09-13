from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from .identity import Subject

_RECEIPT_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class InvalidationEpoch:
    producer: Subject
    generation: int
    event_id: str
    receipt: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.generation < 0:
            raise ValueError("REFUSED_NEGATIVE_EPOCH")
        if not self.event_id.strip():
            raise ValueError("REFUSED_EMPTY_EVENT_ID")
        if not _RECEIPT_RE.fullmatch(self.receipt):
            raise ValueError("REFUSED_INVALID_EPOCH_RECEIPT")
        if self.observed_at.tzinfo is None:
            raise ValueError("REFUSED_NAIVE_EPOCH_TIME")
