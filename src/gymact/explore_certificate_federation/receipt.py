from dataclasses import dataclass
import hashlib
import json

from .authority import ActionClass
from .refusal import FederationRefusal
from .subject import Subject


@dataclass(frozen=True)
class Receipt:
    subject: Subject
    evidence_ids: tuple[str, ...]
    authority: ActionClass = ActionClass.VERIFY
    actuation_performed: bool = False

    def __post_init__(self) -> None:
        if not self.evidence_ids or self.actuation_performed or self.authority is ActionClass.DO:
            raise FederationRefusal("INVALID_RECEIPT_AUTHORITY")

    def body(self) -> dict[str, object]:
        return {"subject": self.subject.identity, "evidence": sorted(self.evidence_ids), "authority": self.authority.value, "actuation_performed": False}

    @property
    def digest(self) -> str:
        payload = json.dumps(self.body(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


def replay(receipt: Receipt, expected_digest: str) -> bool:
    if receipt.actuation_performed:
        raise FederationRefusal("RECEIPT_REPORTS_ACTUATION")
    if receipt.digest != expected_digest:
        raise FederationRefusal("RECEIPT_DRIFT")
    return True
