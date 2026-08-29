from __future__ import annotations

from enum import StrEnum


class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    BUILD_BROKEN = "BUILD_BROKEN"
    REFUSED = "REFUSED"


def classify(*, refused: bool, hard_failure: bool, exact: bool, independent: bool) -> Standing:
    if refused:
        return Standing.REFUSED
    if hard_failure:
        return Standing.BUILD_BROKEN
    if exact and independent:
        return Standing.PARTIAL_ALIVE
    return Standing.UNKNOWN
