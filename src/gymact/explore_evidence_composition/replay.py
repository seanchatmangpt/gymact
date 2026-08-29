from __future__ import annotations

from .receipt import Receipt
from .refusal import RefusalCode, Refused


def replay(receipt: Receipt, expected_digest: str) -> str:
    if receipt.actuation_performed:
        raise Refused(RefusalCode.RECEIPT_DRIFT, "evidence receipt reports consequential actuation")
    if receipt.digest != expected_digest:
        raise Refused(RefusalCode.RECEIPT_DRIFT, "receipt digest mismatch")
    return "REPLAY_MATCH"
