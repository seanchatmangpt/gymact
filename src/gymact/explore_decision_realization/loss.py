from dataclasses import dataclass

from .decision import Decision
from .errors import Refused
from .outcome import RealizedOutcome

@dataclass(frozen=True, slots=True)
class RealizationLoss:
    false_independent: float = 1.0
    false_dependent: float = 0.35
    defer_base: float = 0.15

    def __post_init__(self) -> None:
        if min(self.false_independent, self.false_dependent, self.defer_base) < 0:
            raise Refused("INVALID_LOSS_MATRIX")

    def score(self, decision: Decision, outcome: RealizedOutcome) -> float:
        if decision is Decision.INDEPENDENT:
            classification = 0.0 if outcome.actually_independent else self.false_independent
        elif decision is Decision.DEPENDENT:
            classification = self.false_dependent if outcome.actually_independent else 0.0
        else:
            classification = max(0.0, self.defer_base + outcome.acquisition_cost - outcome.information_gain)
        return classification + outcome.consequence_cost
