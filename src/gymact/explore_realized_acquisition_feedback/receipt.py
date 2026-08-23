from dataclasses import dataclass, asdict
import hashlib
import json

@dataclass(frozen=True)
class FeedbackReceipt:
    subject: str
    policy: str
    standing: str
    actuation_performed: bool = False

    def digest(self) -> str:
        body = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(body).hexdigest()

def replay(receipt: FeedbackReceipt, digest: str) -> bool:
    return not receipt.actuation_performed and receipt.digest() == digest
