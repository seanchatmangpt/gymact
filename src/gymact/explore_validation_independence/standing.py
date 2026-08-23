from enum import IntEnum

class Standing(IntEnum):
    UNKNOWN = 0
    PARTIAL_ALIVE = 1
    ALIVE = 2
    BUILD_BROKEN = 3

def combine(values: tuple[Standing, ...]) -> Standing:
    if not values:
        return Standing.UNKNOWN
    if Standing.BUILD_BROKEN in values:
        return Standing.BUILD_BROKEN
    if Standing.UNKNOWN in values:
        return Standing.UNKNOWN
    if Standing.PARTIAL_ALIVE in values:
        return Standing.PARTIAL_ALIVE
    return Standing.ALIVE
