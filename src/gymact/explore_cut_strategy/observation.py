from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from .epoch import ProducerEpoch

class Outcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"

@dataclass(frozen=True)
class Observation:
    epoch: ProducerEpoch
    scope: str
    outcome: Outcome
    evidence_id: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.scope.strip() or not self.evidence_id.strip():
            raise ValueError("REFUSED_INCOMPLETE_OBSERVATION")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("REFUSED_NAIVE_OBSERVATION_TIME")
        if self.observed_at < self.epoch.observed_at:
            raise ValueError("REFUSED_PRE_EPOCH_OBSERVATION")
