from dataclasses import dataclass
from datetime import datetime
import re
from .subject import Subject

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

@dataclass(frozen=True)
class ProducerEpoch:
    subject: Subject
    generation: int
    receipt: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.generation < 0:
            raise ValueError("REFUSED_INVALID_GENERATION")
        if not _HEX64.fullmatch(self.receipt):
            raise ValueError("REFUSED_INVALID_RECEIPT")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("REFUSED_NAIVE_EPOCH_TIME")

    def newer_than(self, other: "ProducerEpoch") -> bool:
        return self.subject.repo == other.subject.repo and self.generation > other.generation
