from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

SCHEMA = "gymact.explore-evidence-calibration/1"


@dataclass(frozen=True)
class QualificationReceipt:
    payload: dict[str, object]
    digest: str


def issue(payload: dict[str, object]) -> QualificationReceipt:
    body = dict(payload)
    body["schema"] = SCHEMA
    body["actuation_performed"] = False
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return QualificationReceipt(body, hashlib.sha256(canonical).hexdigest())


def replay(receipt: QualificationReceipt) -> bool:
    schema_valid = receipt.payload.get("schema") == SCHEMA
    authority_valid = receipt.payload.get("actuation_performed") is False
    if not schema_valid or not authority_valid:
        return False
    canonical = json.dumps(receipt.payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest() == receipt.digest
