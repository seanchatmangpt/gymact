from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from .refusal import Refused

@dataclass(frozen=True)
class Receipt:
    subject: str
    primal_engine: str
    oracle_engine: str
    cost_gap: str
    standing: str
    authority: str = "VERIFY"
    actuation_performed: bool = False
    def body(self) -> dict[str, object]: return asdict(self)
    @property
    def digest(self) -> str:
        return sha256(json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def replay(receipt: Receipt, digest: str) -> bool:
    if receipt.authority != "VERIFY" or receipt.actuation_performed:
        raise Refused("RECEIPT_AUTHORITY_DRIFT")
    if receipt.digest != digest:
        raise Refused("RECEIPT_DRIFT")
    return True
