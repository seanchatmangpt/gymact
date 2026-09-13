from enum import IntEnum


class Standing(IntEnum):
    BUILD_BROKEN = 0
    UNSUPPORTED = 1
    UNKNOWN = 2
    PARTIAL_ALIVE = 3
    ALIVE = 4


def failure_dominant(states: list[Standing]) -> Standing:
    if not states:
        return Standing.UNKNOWN
    if Standing.BUILD_BROKEN in states:
        return Standing.BUILD_BROKEN
    return min(states)
