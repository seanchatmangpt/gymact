from dataclasses import dataclass
from datetime import datetime
from .epoch import ProducerEpoch

@dataclass(frozen=True)
class EvidenceCut:
    cut_id: str
    generation: int
    epochs: tuple[ProducerEpoch, ...]
    valid_from: datetime
    valid_until: datetime

    def __post_init__(self) -> None:
        if self.generation < 0 or not self.cut_id.strip():
            raise ValueError("REFUSED_INVALID_CUT")
        if self.valid_from.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("REFUSED_NAIVE_CUT_LEASE")
        if self.valid_until <= self.valid_from:
            raise ValueError("REFUSED_INVALID_CUT_LEASE")
        repos=[e.subject.repo for e in self.epochs]
        if len(repos) != len(set(repos)):
            raise ValueError("REFUSED_DUPLICATE_PRODUCER")

    def epoch_map(self) -> dict[str, ProducerEpoch]:
        return {e.subject.repo: e for e in self.epochs}

    def is_active(self, now: datetime) -> bool:
        return self.valid_from <= now < self.valid_until
