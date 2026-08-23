import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from .subject import Refusal, Subject


class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def require(action: ActionClass) -> None:
    if action is ActionClass.DO:
        raise Refusal("REFUSED_UNRECEIPTED_ACTUATION")


@dataclass(frozen=True, slots=True)
class AcquisitionReceipt:
    subject: Subject
    strategy: str
    rail_fingerprints: tuple[str, ...]
    store: str
    standing: str
    actuation_performed: bool = False

    def body(self) -> dict[str, object]:
        return {
            "schema": "gymact.explore-verification-acquisition/1",
            "subject": self.subject.identity,
            "strategy": self.strategy,
            "rail_fingerprints": sorted(self.rail_fingerprints),
            "store": self.store,
            "standing": self.standing,
            "actuation_performed": self.actuation_performed,
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


def replay(receipt: AcquisitionReceipt, expected_digest: str) -> bool:
    return not receipt.actuation_performed and receipt.digest == expected_digest
