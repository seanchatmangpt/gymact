from dataclasses import dataclass
import hashlib
import json

from .decision import DecisionIdentity
from .standing import Standing

@dataclass(frozen=True, slots=True)
class Receipt:
    subject_key: str
    decision_id: str
    policy_generation: int
    strategy: str
    standing: Standing
    realization_generation: int
    authority: str = "SELECT"
    actuation_performed: bool = False

    def body(self) -> dict[str, object]:
        return {
            "actuation_performed": self.actuation_performed,
            "authority": self.authority,
            "decision_id": self.decision_id,
            "policy_generation": self.policy_generation,
            "realization_generation": self.realization_generation,
            "standing": self.standing.value,
            "strategy": self.strategy,
            "subject": self.subject_key,
        }

    def digest(self) -> str:
        payload = json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()


def manufacture(decision: DecisionIdentity, strategy: str, standing: Standing, realization_generation: int) -> Receipt:
    return Receipt(decision.subject.key, decision.decision_id, decision.generation, strategy, standing, realization_generation)
