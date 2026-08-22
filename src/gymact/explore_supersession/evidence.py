from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .epoch import Epoch
from .subject import Subject


class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, order=True)
class Evidence:
    subject: Subject
    epoch: Epoch
    source: str
    scope: str
    outcome: Outcome
    evidence_id: str

    def key(self) -> tuple[str, str, str]:
        return self.source, self.scope, self.evidence_id
