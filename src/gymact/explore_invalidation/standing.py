from __future__ import annotations
from .event import InvalidationEvent

POSITIVE = {"PARTIAL_ALIVE", "ALIVE"}

def affected_standing(previous: str, event: InvalidationEvent) -> str:
    if event.kind in {"BUILD_BROKEN", "BLOCKED"}:
        return "BLOCKED"
    if event.kind == "RECOVERED":
        return "REQUALIFYING"
    if previous in POSITIVE:
        return "UNKNOWN"
    return previous
