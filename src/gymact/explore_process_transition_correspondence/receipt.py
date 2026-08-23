from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .identity import Refused, Subject
from .standing import Standing


@dataclass(frozen=True, slots=True)
class Receipt:
    subject: Subject
    standing: Standing
    obligations: tuple[str, ...]
    actuation_performed: bool = False

    def body(self) -> dict[str, object]:
        if self.actuation_performed:
            raise Refused("REFUSED_UNRECEIPTED_ACTUATION")
        return {
            "schema": "gymact.explore-process-transition-correspondence/1",
            "subject": self.subject.canonical,
            "standing": self.standing.value,
            "obligations": sorted(self.obligations),
            "actuation_performed": False,
        }

    def digest(self) -> str:
        payload = json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()
