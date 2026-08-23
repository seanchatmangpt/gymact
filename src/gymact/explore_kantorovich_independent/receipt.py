from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .identity import VerificationSubject
from .refusal import IndependentVerifierRefusal
from .witness import IndependentWitness


def _fraction(value: object) -> str:
    return str(value)


@dataclass(frozen=True)
class VerificationReceipt:
    schema: str
    subject: str
    engine: str
    primal: str
    dual: str
    gap: str
    authority: str
    actuation_performed: bool
    digest: str


def issue_receipt(subject: VerificationSubject, witness: IndependentWitness) -> VerificationReceipt:
    body = {
        "schema": "gymact.kantorovich-independent-verification/1",
        "subject": subject.identity,
        "engine": witness.engine,
        "primal": _fraction(witness.primal),
        "dual": _fraction(witness.dual),
        "gap": _fraction(witness.gap),
        "authority": "VERIFY",
        "actuation_performed": False,
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return VerificationReceipt(**body, digest=digest)


def replay(receipt: VerificationReceipt) -> bool:
    if receipt.authority != "VERIFY" or receipt.actuation_performed:
        raise IndependentVerifierRefusal("RECEIPT_AUTHORITY_DRIFT", "verification receipt cannot claim consequential actuation")
    body = asdict(receipt)
    supplied = body.pop("digest")
    expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if supplied != expected:
        raise IndependentVerifierRefusal("RECEIPT_DIGEST_MISMATCH", f"{supplied}!={expected}")
    return True
