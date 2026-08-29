from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from .refusals import refuse


@dataclass(frozen=True, slots=True)
class ReceiptBody:
    subject: str
    selector: str
    standing: str
    authority: str = "SELECT"
    actuation_performed: bool = False

    def canonical(self) -> bytes:
        if self.actuation_performed:
            raise refuse("UNRECEIPTED_ACTUATION", "EXPLORE receipts cannot report consequential actuation")
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True, slots=True)
class Receipt:
    body: ReceiptBody
    digest: str

    @classmethod
    def issue(cls, body: ReceiptBody) -> "Receipt":
        return cls(body=body, digest=hashlib.sha256(body.canonical()).hexdigest())

    def replay(self) -> bool:
        return self.digest == hashlib.sha256(self.body.canonical()).hexdigest()
