from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Budget:
    cost: Fraction
    latency_ms: int
    samples: int

    def __post_init__(self) -> None:
        if self.cost < 0 or self.latency_ms < 0 or self.samples < 0:
            raise ValueError("REFUSED_INVALID_BUDGET")

    def admits(self, *, cost: Fraction, latency_ms: int, samples: int = 1) -> bool:
        return cost <= self.cost and latency_ms <= self.latency_ms and samples <= self.samples

    def consume(self, *, cost: Fraction, latency_ms: int, samples: int = 1) -> "Budget":
        if not self.admits(cost=cost, latency_ms=latency_ms, samples=samples):
            raise ValueError("REFUSED_BUDGET_EXCEEDED")
        return Budget(self.cost - cost, self.latency_ms - latency_ms, self.samples - samples)
