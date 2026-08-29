from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction

from .refusal import DualityRefusal
from .subject import Subject


@dataclass(frozen=True)
class Receipt:
    subject: Subject
    primal: Fraction
    dual: Fraction
    authority: str
    actuation_performed: bool
    digest: str


def _body(subject: Subject, primal: Fraction, dual: Fraction, authority: str, actuation: bool) -> dict[str, str | bool]:
    return {
        "repo": subject.repo,
        "sha": subject.sha,
        "semantic": subject.semantic,
        "primal": str(primal),
        "dual": str(dual),
        "authority": authority,
        "actuation_performed": actuation,
    }


def manufacture_receipt(subject: Subject, primal: Fraction, dual: Fraction) -> Receipt:
    body = _body(subject, primal, dual, "VERIFY", False)
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return Receipt(subject, primal, dual, "VERIFY", False, digest)


def replay(receipt: Receipt) -> None:
    if receipt.actuation_performed:
        raise DualityRefusal("RECEIPT_ACTUATION", "verification receipt cannot report actuation")
    body = _body(receipt.subject, receipt.primal, receipt.dual, receipt.authority, receipt.actuation_performed)
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != receipt.digest:
        raise DualityRefusal("RECEIPT_DRIFT", "receipt digest mismatch")
