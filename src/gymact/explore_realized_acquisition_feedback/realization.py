from dataclasses import dataclass
from fractions import Fraction

from .subject import Refusal


@dataclass(frozen=True)
class AcquisitionRealization:
    sensor: str
    predicted_gain: Fraction
    realized_gain: Fraction
    cost: Fraction
    latency_ms: int

    def __post_init__(self) -> None:
        invalid_value = min(self.predicted_gain, self.realized_gain, self.cost) < 0
        if not self.sensor or invalid_value or self.latency_ms < 0:
            raise Refusal("REFUSED_INVALID_REALIZATION")

    @property
    def gain_error(self) -> Fraction:
        return self.realized_gain - self.predicted_gain
