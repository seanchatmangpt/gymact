from __future__ import annotations

from enum import StrEnum


class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    ALIVE = "ALIVE"
    BUILD_BROKEN = "BUILD_BROKEN"


def combine(values: tuple[Standing, ...], *, exact_subject_executed: bool) -> Standing:
    if Standing.BUILD_BROKEN in values:
        return Standing.BUILD_BROKEN
    if not exact_subject_executed:
        return Standing.UNKNOWN
    if values and all(value is Standing.ALIVE for value in values):
        return Standing.PARTIAL_ALIVE
    if Standing.PARTIAL_ALIVE in values or Standing.ALIVE in values:
        return Standing.PARTIAL_ALIVE
    return Standing.UNKNOWN
