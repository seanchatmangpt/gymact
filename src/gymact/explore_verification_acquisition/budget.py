from dataclasses import dataclass

from .capability import RailCapability
from .subject import Refusal


@dataclass(frozen=True, slots=True)
class AcquisitionBudget:
    max_cost_millis: int
    max_latency_millis: int
    max_rails: int

    def __post_init__(self) -> None:
        if self.max_cost_millis <= 0 or self.max_latency_millis <= 0 or self.max_rails <= 0:
            raise Refusal("REFUSED_INVALID_ACQUISITION_BUDGET")

    def admits(self, rails: tuple[RailCapability, ...]) -> bool:
        return (
            len(rails) <= self.max_rails
            and sum(rail.cost_millis for rail in rails) <= self.max_cost_millis
            and sum(rail.latency_millis for rail in rails) <= self.max_latency_millis
        )
