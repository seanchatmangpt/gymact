import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AcquisitionReceipt:
    subject: str
    policy: str
    selected_sensor: str | None
    standing: str
    step: int
    actuation_performed: bool = False

    def digest(self) -> str:
        if self.actuation_performed:
            raise ValueError("REFUSED_RECEIPT_ACTUATION")
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


def replay(receipt: AcquisitionReceipt, expected_digest: str) -> bool:
    return receipt.digest() == expected_digest
