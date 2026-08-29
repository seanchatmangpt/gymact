from dataclasses import dataclass
import hashlib
import json

from .standing import Standing
from .subject import Subject


@dataclass(frozen=True, slots=True)
class Receipt:
    subject: Subject
    transport_digest: str
    standing: Standing
    authority: str = "SELECT"
    actuation_performed: bool = False

    def body(self) -> dict[str, object]:
        return {
            "schema": "gymact.decision-transport/1",
            "subject": self.subject.identity,
            "transport_digest": self.transport_digest,
            "standing": self.standing.value,
            "authority": self.authority,
            "actuation_performed": self.actuation_performed,
        }

    def digest(self) -> str:
        payload = json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()
