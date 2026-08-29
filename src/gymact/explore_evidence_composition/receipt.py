from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .standing import Standing
from .subject import Subject


@dataclass(frozen=True, slots=True)
class Receipt:
    subject: Subject
    standing: Standing
    evidence_ids: tuple[str, ...]
    selector: str
    authority: str = "SELECT"
    actuation_performed: bool = False

    @property
    def body(self) -> dict[str, object]:
        return {
            "schema": "gymact.explore-evidence-composition/1",
            "subject": self.subject.key,
            "standing": self.standing.value,
            "evidence_ids": sorted(self.evidence_ids),
            "selector": self.selector,
            "authority": self.authority,
            "actuation_performed": self.actuation_performed,
        }

    @property
    def digest(self) -> str:
        payload = json.dumps(self.body, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()
