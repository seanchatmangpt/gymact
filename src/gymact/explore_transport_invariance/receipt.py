from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .authority import Action
from .refusal import require
from .subject import Subject


@dataclass(frozen=True, slots=True)
class Receipt:
    subject: str
    strategy: str
    standing: str
    authority: str
    actuation_performed: bool
    digest: str


def issue(subject: Subject, strategy: str, standing: str) -> Receipt:
    payload = {
        "subject": subject.identity,
        "strategy": strategy,
        "standing": standing,
        "authority": Action.SELECT.value,
        "actuation_performed": False,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return Receipt(**payload, digest=digest)


def replay(receipt: Receipt) -> bool:
    require(not receipt.actuation_performed, "RECEIPT_DRIFT", "receipt reports actuation")
    payload = asdict(receipt)
    expected = payload.pop("digest")
    actual = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    require(actual == expected, "RECEIPT_DRIFT", "digest mismatch")
    return True
