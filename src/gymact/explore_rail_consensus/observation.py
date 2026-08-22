from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .rail import VerificationRail
from .subject import Refusal

class Outcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"

@dataclass(frozen=True, slots=True)
class RailObservation:
    rail: VerificationRail
    run_id: str
    outcome: Outcome
    observed_at: datetime
    artifact_digest: str = ""

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise Refusal("REFUSED_NAIVE_OBSERVATION_TIME")
        if not self.run_id:
            raise Refusal("REFUSED_MISSING_RUN_ID")
        if self.observed_at > datetime.now(timezone.utc):
            raise Refusal("REFUSED_FUTURE_OBSERVATION")

    @property
    def evidence_id(self) -> str:
        return f"{self.rail.fingerprint}:{self.run_id}:{self.artifact_digest}:{self.outcome.value}"
