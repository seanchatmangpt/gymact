from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .refusal import Refused

SCHEMA = "gymact.explore-kantorovich-ambiguity/1"

def canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

@dataclass(frozen=True)
class Receipt:
    body: dict[str, Any]
    digest: str

def issue(body: Mapping[str, Any]) -> Receipt:
    data = dict(body)
    if data.get("actuation_performed") is not False:
        raise Refused("RECEIPT_REQUIRES_NO_ACTUATION")
    if data.get("authority") not in {"OBSERVE", "SELECT", "CONSTRUCT", "VERIFY"}:
        raise Refused("RECEIPT_AUTHORITY_INVALID")
    data["schema"] = SCHEMA
    return Receipt(data, hashlib.sha256(canonical(data)).hexdigest())

def replay(receipt: Receipt) -> bool:
    if receipt.body.get("actuation_performed") is not False:
        raise Refused("REPLAY_REPORTS_ACTUATION")
    expected = hashlib.sha256(canonical(receipt.body)).hexdigest()
    if expected != receipt.digest:
        raise Refused("RECEIPT_DIGEST_MISMATCH")
    return True
