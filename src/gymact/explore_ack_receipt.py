from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
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
    standing = "ALIVE" if result.complete and result.safe else "REQUALIFYING" if result.safe else "BLOCKED"
    return Receipt(subject, event_id, result.protocol, standing, hashlib.sha256(evidence).hexdigest())

def replay(receipt: Receipt, evidence: bytes) -> bool:
    return receipt.evidence_digest == hashlib.sha256(evidence).hexdigest()
