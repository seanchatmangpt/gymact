from dataclasses import dataclass
from datetime import datetime, timezone

from .refusals import FusionRefused
from .sensor import SensorIdentity


@dataclass(frozen=True, slots=True)
class Observation:
    sensor: SensorIdentity
    projection_digest: str
    verdict: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.verdict not in {"CURRENT", "STALE", "AMBIGUOUS"}:
            raise FusionRefused("REFUSED_INVALID_VERDICT")
        if len(self.projection_digest) != 64:
            raise FusionRefused("REFUSED_INVALID_PROJECTION_DIGEST")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise FusionRefused("REFUSED_NAIVE_OBSERVATION_TIME")
        if self.observed_at > datetime.now(timezone.utc):
            raise FusionRefused("REFUSED_FUTURE_OBSERVATION")
