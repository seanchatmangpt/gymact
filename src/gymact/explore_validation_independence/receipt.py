import hashlib
import json
from dataclasses import dataclass

from .standing import Standing
from .subject import Subject


@dataclass(frozen=True)
class Receipt:
    subject: Subject
    strategy: str
    mode: str
    standing: Standing
    evidence_ids: tuple[str, ...]
    authority: str = "SELECT"
    actuation_performed: bool = False

    @property
    def body(self) -> dict[str, object]:
        return {
            "schema": "gymact.explore-validation-independence/1",
            "subject": self.subject.key,
            "strategy": self.strategy,
            "mode": self.mode,
            "standing": self.standing.name,
            "evidence_ids": sorted(self.evidence_ids),
            "authority": self.authority,
            "actuation_performed": self.actuation_performed,
        }

    @property
    def digest(self) -> str:
        raw = json.dumps(self.body, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()
