from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction

from .refusal import Refused
from .subject import Subject


def _unit(value: Fraction, name: str) -> None:
    if value < 0 or value > 1:
        raise Refused("REFUSED_INVALID_PROPENSITY", name)


@dataclass(frozen=True, slots=True)
class LoggedDecision:
    subject: Subject
    decision_id: str
    context_id: str
    action: str
    realized_gain: Fraction
    behavior_probability: Fraction
    target_probability: Fraction
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.decision_id or not self.context_id or not self.action:
            raise Refused("REFUSED_INVALID_LOGGED_DECISION")
        if self.realized_gain < 0:
            raise Refused("REFUSED_NEGATIVE_REALIZED_GAIN", self.decision_id)
        _unit(self.behavior_probability, "behavior_probability")
        _unit(self.target_probability, "target_probability")
        if self.behavior_probability == 0:
            raise Refused("REFUSED_ZERO_BEHAVIOR_PROPENSITY", self.decision_id)
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise Refused("REFUSED_NAIVE_OBSERVATION_TIME", self.decision_id)
