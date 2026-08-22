from dataclasses import dataclass
from enum import Enum
import hashlib
import json

from .subject import Refusal, Subject

class ActionClass(str, Enum):
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"

def require(action: ActionClass) -> None:
    if action is ActionClass.DO:
        raise Refusal("REFUSED_UNRECEIPTED_ACTUATION")

@dataclass(frozen=True, slots=True)
class QualificationReceipt:
    subject: Subject
    strategy: str
    standing: str
    cluster_count: int
    store: str
    actuation_performed: bool = False

    def body(self) -> dict[str, object]:
        return {
            "schema": "gymact.explore-rail-consensus/1",
            "subject": self.subject.identity,
            "strategy": self.strategy,
            "standing": self.standing,
            "cluster_count": self.cluster_count,
            "store": self.store,
            "actuation_performed": self.actuation_performed,
        }

    @property
    def digest(self) -> str:
        payload = json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()

def replay(receipt: QualificationReceipt, expected_digest: str) -> bool:
    return receipt.actuation_performed is False and receipt.digest == expected_digest
