from __future__ import annotations

from enum import StrEnum

from .obligation import ObligationState


class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    BUILD_BROKEN = "BUILD_BROKEN"
    REFUSED = "REFUSED"


def standing(states: list[ObligationState], *, blocked: bool = False) -> Standing:
    if ObligationState.REFUSED in states:
        return Standing.REFUSED
    if blocked or ObligationState.FAIL in states:
        return Standing.BUILD_BROKEN
    if not states or ObligationState.UNKNOWN in states:
        return Standing.UNKNOWN
    return Standing.PARTIAL_ALIVE
