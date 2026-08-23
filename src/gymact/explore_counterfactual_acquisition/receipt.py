import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from .refusal import Refused
from .subject import Subject


def _fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _digest(body: dict[str, Any]) -> str:
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class EvaluationReceipt:
    body: dict[str, Any]
    digest: str


def issue(
    *,
    subject: Subject,
    strategy: str,
    estimate: Fraction,
    standing: str,
    storage: str,
) -> EvaluationReceipt:
    body: dict[str, Any] = {
        "schema": "gymact.explore-counterfactual-acquisition/1",
        "subject": subject.exact,
        "strategy": strategy,
        "estimate": _fraction(estimate),
        "standing": standing,
        "storage": storage,
        "action": "CONSTRUCT",
        "actuation_performed": False,
    }
    return EvaluationReceipt(body=body, digest=_digest(body))


def replay(receipt: EvaluationReceipt) -> bool:
    if receipt.body.get("actuation_performed") is not False:
        raise Refused("REFUSED_RECEIPT_REPORTS_ACTUATION")
    return _digest(receipt.body) == receipt.digest
