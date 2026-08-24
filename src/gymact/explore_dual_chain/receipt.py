from dataclasses import dataclass
import hashlib
import json
from .refusal import DualChainRefusal

@dataclass(frozen=True)
class Receipt:
    body: dict[str, object]
    digest: str

def manufacture(body: dict[str, object]) -> Receipt:
    if body.get("authority") != "VERIFY" or body.get("actuation_performed") is not False:
        raise DualChainRefusal("INVALID_RECEIPT_AUTHORITY")
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return Receipt(body, hashlib.sha256(raw).hexdigest())

def replay(receipt: Receipt) -> bool:
    return manufacture(receipt.body).digest == receipt.digest
