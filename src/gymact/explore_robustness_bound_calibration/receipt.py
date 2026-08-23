from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from .refusal import Refused, REFUSED_UNRECEIPTED_ACTUATION
from .subject import Subject


@dataclass(frozen=True, slots=True)
class Receipt:
    subject: str
    calibration_digest: str
    standing: str
    action: str = "CONSTRUCT"
    actuation_performed: bool = False

    def body(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.body().encode()).hexdigest()

    @classmethod
    def create(cls, subject: Subject, calibration_digest: str, standing: str) -> "Receipt":
        return cls(subject.value, calibration_digest, standing)


def require_action(action: str) -> None:
    if action == "DO":
        raise Refused(REFUSED_UNRECEIPTED_ACTUATION)
    if action not in {"OBSERVE", "SELECT", "CONSTRUCT", "VERIFY"}:
        raise ValueError(action)


def replay(receipt: Receipt, expected_digest: str) -> bool:
    return not receipt.actuation_performed and receipt.digest == expected_digest
