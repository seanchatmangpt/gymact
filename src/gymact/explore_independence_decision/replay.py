from __future__ import annotations

from .errors import Refused
from .receipt import Receipt


def replay(receipt: Receipt, expected_digest: str) -> str:
    if receipt.actuation_performed:
        raise Refused("REPORTED_AMBIENT_ACTUATION")
    if receipt.authority != "SELECT":
        raise Refused("AUTHORITY_DRIFT")
    if receipt.digest() != expected_digest:
        raise Refused("RECEIPT_DRIFT")
    return "REPLAY_MATCH"
