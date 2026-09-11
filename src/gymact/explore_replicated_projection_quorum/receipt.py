from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .refusal import Refused


class ActionClass(StrEnum):
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    DO = "DO"


def require_action(action: ActionClass) -> None:
    if action is ActionClass.DO:
        raise Refused("REFUSED_UNRECEIPTED_ACTUATION")


@dataclass(frozen=True, slots=True)
class QualificationReceipt:
    body: dict[str, Any]
    digest: str

    @classmethod
    def create(cls, body: dict[str, Any]) -> QualificationReceipt:
        safe = dict(body)
        safe["actuation_performed"] = False
        safe["schema"] = "gymact.explore-replicated-projection-quorum/1"
        raw = json.dumps(safe, sort_keys=True, separators=(",", ":")).encode()
        return cls(safe, hashlib.sha256(raw).hexdigest())


def replay(receipt: QualificationReceipt) -> bool:
    if receipt.body.get("actuation_performed") is not False:
        return False
    raw = json.dumps(receipt.body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest() == receipt.digest
