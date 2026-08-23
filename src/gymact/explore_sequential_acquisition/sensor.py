from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class SensorCapability:
    name: str
    family: str
    domain: str
    generation: int
    digest: str
    cost: Fraction
    latency_ms: int

    def __post_init__(self) -> None:
        if not self.name or not self.family or not self.domain or self.generation < 0:
            raise ValueError("REFUSED_INVALID_SENSOR")
        if len(self.digest) != 64 or any(c not in "0123456789abcdef" for c in self.digest):
            raise ValueError("REFUSED_INVALID_SENSOR_DIGEST")
        if self.cost < 0 or self.latency_ms < 0:
            raise ValueError("REFUSED_INVALID_SENSOR_COST")

    @property
    def independence_key(self) -> tuple[str, str]:
        return self.family, self.domain
