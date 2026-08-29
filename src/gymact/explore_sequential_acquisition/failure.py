from dataclasses import dataclass
from random import Random


@dataclass(frozen=True)
class FailureWorld:
    seed: int
    dropout_rate: float
    correlation_rate: float

    def failed(self, sensors: tuple[str, ...]) -> tuple[str, ...]:
        rng = Random(self.seed)
        out = []
        for sensor in sorted(sensors):
            if rng.random() < self.dropout_rate:
                out.append(sensor)
        return tuple(out)

    def correlated(self, families: tuple[str, ...]) -> tuple[str, ...]:
        rng = Random(self.seed ^ 0xA5A5)
        return tuple(f for f in sorted(families) if rng.random() < self.correlation_rate)
