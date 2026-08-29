from __future__ import annotations

from .errors import Refused
from .receipt import Receipt


def replay(receipt: Receipt, expected_digest: str) -> str:
    if receipt.digest() != expected_digest:
        raise Refused("REPLAY_DIGEST_MISMATCH")
    if receipt.actuation_performed:
        raise Refused("REPLAY_ACTUATION_DRIFT")
    return "REPLAY_MATCH"
