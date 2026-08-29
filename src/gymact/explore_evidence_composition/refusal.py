from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RefusalCode(StrEnum):
    INVALID_SUBJECT = "INVALID_SUBJECT"
    CYCLIC_EVIDENCE_GRAPH = "CYCLIC_EVIDENCE_GRAPH"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    DIVERGENT_FRONTIER = "DIVERGENT_FRONTIER"
    INDEPENDENCE_COLLISION = "INDEPENDENCE_COLLISION"
    UNSATISFIED_DEPENDENCY = "UNSATISFIED_DEPENDENCY"
    INVALID_INTERVAL = "INVALID_INTERVAL"
    UNRECEIPTED_ACTUATION = "UNRECEIPTED_ACTUATION"
    RECEIPT_DRIFT = "RECEIPT_DRIFT"


@dataclass(frozen=True, slots=True)
class Refused(Exception):
    code: RefusalCode
    detail: str

    def __str__(self) -> str:
        return f"REFUSED[{self.code}]: {self.detail}"
