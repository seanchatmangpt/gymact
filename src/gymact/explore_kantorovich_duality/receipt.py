from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from .refusal import refuse
from .standing import Standing


@dataclass(frozen=True)
class Receipt:
    subject: str
    optimum: str
    standing: Standing
    authority: str = "VERIFY"
    actuation_performed: bool = False

    def digest(self) -> str:
        if self.actuation_performed:
            refuse("RECEIPT_ACTUATION", "duality receipt cannot report actuation")
        body = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(body.encode()).hexdigest()
