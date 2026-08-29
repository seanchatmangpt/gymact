from enum import StrEnum


class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    BUILD_BROKEN = "BUILD_BROKEN"


def combine(states: tuple[Standing, ...]) -> Standing:
    if Standing.BUILD_BROKEN in states:
        return Standing.BUILD_BROKEN
    if states and all(state is Standing.PARTIAL_ALIVE for state in states):
        return Standing.PARTIAL_ALIVE
    return Standing.UNKNOWN
