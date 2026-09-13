from __future__ import annotations

from enum import StrEnum


class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    ALIVE = "ALIVE"
    BLOCKED = "BLOCKED"
    BUILD_BROKEN = "BUILD_BROKEN"
    UNSUPPORTED = "UNSUPPORTED"


def combine(states: list[Standing]) -> Standing:
    if Standing.BUILD_BROKEN in states:
        return Standing.BUILD_BROKEN
    if Standing.UNSUPPORTED in states:
        return Standing.UNSUPPORTED
    if Standing.UNKNOWN in states:
        return Standing.UNKNOWN
    if states and all(s is Standing.ALIVE for s in states):
        return Standing.PARTIAL_ALIVE
    return Standing.PARTIAL_ALIVE
