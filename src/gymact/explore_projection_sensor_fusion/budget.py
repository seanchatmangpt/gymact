from dataclasses import dataclass
from fractions import Fraction

from .acquisition import AcquisitionCandidate
from .refusals import FusionRefused


@dataclass(frozen=True, slots=True)
class Budget:
    cost: Fraction
    latency_ms: int

    def admits(self, candidate: AcquisitionCandidate) -> bool:
        return candidate.cost <= self.cost and candidate.latency_ms <= self.latency_ms


def require_budget(candidate: AcquisitionCandidate, budget: Budget) -> None:
    if not budget.admits(candidate):
        raise FusionRefused("REFUSED_ACQUISITION_BUDGET")
