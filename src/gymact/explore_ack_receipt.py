from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .explore_ack_comparator import Result


@dataclass(frozen=True)
class Receipt:
    subject: str
    event_id: str
    protocol: str
    standing: str
    evidence_digest: str

    def canonical(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()


def make_receipt(subject: str, event_id: str, result: Result, evidence: bytes) -> Receipt:
    if result.complete and result.safe:
        standing = "ALIVE"
    elif result.safe:
        standing = "REQUALIFYING"
    else:
        standing = "BLOCKED"
    evidence_digest = hashlib.sha256(evidence).hexdigest()
    return Receipt(subject, event_id, result.protocol, standing, evidence_digest)


def replay(receipt: Receipt, evidence: bytes) -> bool:
    return receipt.evidence_digest == hashlib.sha256(evidence).hexdigest()
