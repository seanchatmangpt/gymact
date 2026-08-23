from dataclasses import dataclass
from hashlib import sha256
import json
from .errors import Refused

@dataclass(frozen=True)
class Receipt:
    body: dict
    digest: str

    @classmethod
    def issue(cls, body: dict) -> "Receipt":
        if body.get("actuation_performed") is not False:
            raise Refused("REFUSED_ACTUATION_RECEIPT")
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
        return cls(body, sha256(raw).hexdigest())

def replay(receipt: Receipt) -> bool:
    return Receipt.issue(receipt.body).digest == receipt.digest
