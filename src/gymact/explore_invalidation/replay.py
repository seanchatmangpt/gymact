from __future__ import annotations

import hashlib
import json
from dataclasses import replace

from .model import Refusal
from .receipt import SCHEMA, Receipt


def verify_receipt(receipt: Receipt) -> bool:
    if receipt.schema != SCHEMA or receipt.payload.get("actuation_performed") is not False:
        raise Refusal("REFUSED_RECEIPT_AUTHORITY_OR_SCHEMA_DRIFT")
    raw = json.dumps(receipt.payload, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(raw).hexdigest() != receipt.digest:
        raise Refusal("REFUSED_RECEIPT_REPLAY_MISMATCH")
    return True


def tamper(receipt: Receipt, **changes: object) -> Receipt:
    payload = dict(receipt.payload)
    payload.update(changes)
    return replace(receipt, payload=payload)
