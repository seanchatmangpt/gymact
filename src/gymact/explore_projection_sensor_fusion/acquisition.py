from dataclasses import dataclass
from fractions import Fraction

from .refusals import FusionRefused


@dataclass(frozen=True, slots=True)
class AcquisitionCandidate:
    sensor_id: str
    expected_discrimination: Fraction
    independence_gain: Fraction
    cost: Fraction
    latency_ms: int

    def __post_init__(self) -> None:
        if not self.sensor_id or min(self.expected_discrimination, self.independence_gain, self.cost) < 0 or self.latency_ms < 0:
            raise FusionRefused("REFUSED_INVALID_ACQUISITION_CANDIDATE")
