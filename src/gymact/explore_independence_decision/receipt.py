from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .standing import Standing


@dataclass(frozen=True)
class Receipt:
    subject: str
    strategy: str
    decision: str
    standing: Standing
    evidence_generation: int
    authority: str = "SELECT"
    actuation_performed: bool = False

    def body(self) -> dict[str, object]:
        payload = asdict(self)
        payload["standing"] = self.standing.value
        return payload

    def digest(self) -> str:
        encoded = json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
