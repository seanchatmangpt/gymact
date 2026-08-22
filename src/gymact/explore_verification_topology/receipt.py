from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from .subject import Subject

@dataclass(frozen=True)
class QualificationReceipt:
    subject: Subject
    policy: str
    standing: str
    store: str
    collision_classes: int
    actuation_performed: bool = False

    def payload(self) -> dict:
        payload = asdict(self)
        payload["schema"] = "gymact.explore-verification-topology/1"
        return payload

    def digest(self) -> str:
        blob = json.dumps(self.payload(), sort_keys=True, separators=(",", ":")).encode()
        return sha256(blob).hexdigest()

def replay(receipt: QualificationReceipt, expected_digest: str) -> bool:
    return receipt.digest() == expected_digest and not receipt.actuation_performed
