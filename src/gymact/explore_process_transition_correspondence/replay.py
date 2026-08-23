from __future__ import annotations

from .identity import Refused
from .receipt import Receipt


def replay(receipt: Receipt, expected_digest: str) -> bool:
    if receipt.actuation_performed:
        raise Refused("REFUSED_UNRECEIPTED_ACTUATION")
    if receipt.digest() != expected_digest:
        raise Refused("REFUSED_RECEIPT_TAMPER")
    return True
