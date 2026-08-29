from dataclasses import dataclass
from fractions import Fraction

from .belief import BeliefState


@dataclass(frozen=True)
class StopRule:
    confidence: Fraction
    max_steps: int

    def __post_init__(self) -> None:
        if self.confidence <= 0 or self.confidence > 1 or self.max_steps <= 0:
            raise ValueError("REFUSED_INVALID_STOP_RULE")

    def should_stop(self, belief: BeliefState, step: int) -> bool:
        return max(belief.probabilities) >= self.confidence or step >= self.max_steps
