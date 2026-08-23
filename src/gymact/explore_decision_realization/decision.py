from dataclasses import dataclass
from enum import StrEnum

from .errors import Refused
from .subject import Subject

class Decision(StrEnum):
    INDEPENDENT = "INDEPENDENT"
    DEPENDENT = "DEPENDENT"
    DEFER = "DEFER"

@dataclass(frozen=True, slots=True)
class DecisionIdentity:
    subject: Subject
    decision_id: str
    policy: str
    generation: int
    policy_digest: str
    decision: Decision
    decided_at_ns: int
    predicted_loss: float

    def __post_init__(self) -> None:
        if not self.decision_id or not self.policy:
            raise Refused("INVALID_DECISION_IDENTITY")
        if self.generation < 0 or self.decided_at_ns < 0:
            raise Refused("INVALID_DECISION_IDENTITY")
        if len(self.policy_digest) != 64 or any(c not in "0123456789abcdef" for c in self.policy_digest):
            raise Refused("INVALID_DECISION_IDENTITY", "policy digest must be 64-hex")
        if not 0.0 <= self.predicted_loss <= 1.0:
            raise Refused("INVALID_PREDICTED_LOSS")
