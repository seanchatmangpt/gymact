from __future__ import annotations
from dataclasses import dataclass
from .event import InvalidationEvent
from .model import Binding

@dataclass(frozen=True)
class Impact:
    binding: Binding
    reason: str

_REASON = {
    "NEW_HEAD": "SUPERSEDED_SUBJECT",
    "NEW_RECEIPT": "SUPERSEDED_RECEIPT",
    "SCHEMA_CHANGE": "SCHEMA_DRIFT",
    "EXPIRED": "LEASE_EXPIRED",
    "BUILD_BROKEN": "PRODUCER_BUILD_BROKEN",
    "BLOCKED": "PRODUCER_BLOCKED",
    "RECOVERED": "PRODUCER_RECOVERED_REQUALIFY",
}

def direct_impact(binding: Binding, event: InvalidationEvent) -> Impact:
    return Impact(binding=binding, reason=_REASON[event.kind])
