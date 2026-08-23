from dataclasses import dataclass

from .decision import DecisionIdentity
from .errors import Refused
from .subject import Subject


@dataclass(frozen=True, slots=True)
class RealizedOutcome:
    subject: Subject
    decision_id: str
    outcome_id: str
    observed_at_ns: int
    actually_independent: bool
    consequence_cost: float
    information_gain: float = 0.0
    acquisition_cost: float = 0.0
    source: str = "independent_observer"

    def __post_init__(self) -> None:
        if not self.outcome_id or not self.source:
            raise Refused("INVALID_OUTCOME")
        if self.observed_at_ns < 0:
            raise Refused("INVALID_OUTCOME")
        if min(self.consequence_cost, self.information_gain, self.acquisition_cost) < 0:
            raise Refused("INVALID_OUTCOME_VALUE")

    def bind(self, decision: DecisionIdentity) -> None:
        if self.subject != decision.subject or self.decision_id != decision.decision_id:
            raise Refused("FOREIGN_OUTCOME")
        if self.observed_at_ns <= decision.decided_at_ns:
            raise Refused("PREDECISION_OUTCOME")
