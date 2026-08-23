from dataclasses import dataclass, asdict
import hashlib
import json

from .authority import ActionClass
from .subject import Subject


@dataclass(frozen=True, slots=True)
class Receipt:
    subject: Subject
    selector: str
    selected_sensor: str | None
    audit_root: str
    standing: str
    action: ActionClass = ActionClass.CONSTRUCT
    actuation_performed: bool = False

    def body(self) -> dict[str, object]:
        data = asdict(self)
        data["subject"] = self.subject.value
        data["action"] = self.action.value
        return data

    @property
    def digest(self) -> str:
        payload = json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()
