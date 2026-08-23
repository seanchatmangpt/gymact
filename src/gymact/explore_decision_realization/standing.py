from enum import StrEnum
from collections.abc import Iterable

class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    ALIVE = "ALIVE"
    BLOCKED = "BLOCKED"
    BUILD_BROKEN = "BUILD_BROKEN"
    UNSUPPORTED = "UNSUPPORTED"


def combine(states: Iterable[Standing], *, realization_admitted: bool, drifted: bool) -> Standing:
    rows = tuple(states)
    if Standing.BUILD_BROKEN in rows:
        return Standing.BUILD_BROKEN
    if Standing.BLOCKED in rows:
        return Standing.BLOCKED
    if drifted:
        return Standing.PARTIAL_ALIVE
    if realization_admitted and rows and all(row in {Standing.ALIVE, Standing.PARTIAL_ALIVE} for row in rows):
        return Standing.PARTIAL_ALIVE
    if Standing.UNSUPPORTED in rows:
        return Standing.UNSUPPORTED
    return Standing.UNKNOWN
