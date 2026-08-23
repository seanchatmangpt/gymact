from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction


@dataclass(frozen=True)
class ObservationEvidence:
    sensor_digest: str
    outcome: str
    likelihoods: tuple[Fraction, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at > datetime.now(timezone.utc):
            raise ValueError("REFUSED_INVALID_OBSERVATION_TIME")
        if len(self.sensor_digest) != 64 or not self.outcome:
            raise ValueError("REFUSED_INVALID_OBSERVATION")
        if not self.likelihoods or any(x < 0 or x > 1 for x in self.likelihoods):
            raise ValueError("REFUSED_INVALID_LIKELIHOODS")
