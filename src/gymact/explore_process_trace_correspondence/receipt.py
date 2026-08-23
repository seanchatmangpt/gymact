from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json

from .refusal import Refused
from .standing import Standing
from .subject import Subject


@dataclass(frozen=True)
class Receipt:
    subject: Subject
    relation: str
    standing: Standing
    actuation_performed: bool = False

    def body(self) -> dict[str, object]:
        if self.actuation_performed:
            raise Refused("RECEIPT_REPORTS_ACTUATION")
        return {"subject": self.subject.identity, "relation": self.relation, "standing": self.standing.value, "actuation_performed": False}

    def digest(self) -> str:
        encoded = json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


def replay(receipt: Receipt, digest: str) -> bool:
    return receipt.digest() == digest
