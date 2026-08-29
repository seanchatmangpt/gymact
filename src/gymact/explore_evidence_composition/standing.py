from __future__ import annotations

from enum import StrEnum


class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    ALIVE = "ALIVE"
    BUILD_BROKEN = "BUILD_BROKEN"


def compose_standing(values: tuple[Standing, ...]) -> Standing:
    if not values:
        return Standing.UNKNOWN
    if Standing.BUILD_BROKEN in values:
        return Standing.BUILD_BROKEN
    if Standing.UNKNOWN in values:
        return Standing.UNKNOWN
    if Standing.UNSUPPORTED in values:
        return Standing.UNSUPPORTED
    if all(value is Standing.ALIVE for value in values):
        return Standing.ALIVE
    return Standing.PARTIAL_ALIVE
