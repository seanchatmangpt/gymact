from __future__ import annotations

from .observation import Observation
from .receipt import Receipt, make_receipt
from .subject import Subject


def replay(receipt: Receipt, subject: Subject, observations: tuple[Observation, ...]) -> bool:
    rebuilt = make_receipt(subject, receipt.standing, observations)
    if rebuilt.digest != receipt.digest or rebuilt.subject != receipt.subject:
        raise ValueError("REFUSED_RECEIPT_REPLAY_MISMATCH")
    if receipt.actuation_performed:
        raise ValueError("REFUSED_RECEIPT_CLAIMS_ACTUATION")
    return True
