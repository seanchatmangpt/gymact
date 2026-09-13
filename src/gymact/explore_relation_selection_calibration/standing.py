from __future__ import annotations

from enum import StrEnum


class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    BUILD_BROKEN = "BUILD_BROKEN"


def derive(*, admitted_count: int, hard_failure: bool, calibration_complete: bool) -> Standing:
    if hard_failure:
        return Standing.BUILD_BROKEN
    if admitted_count <= 0 or not calibration_complete:
        return Standing.UNKNOWN
    return Standing.PARTIAL_ALIVE
