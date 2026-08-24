from enum import IntEnum


class Standing(IntEnum):
    ALIVE = 0
    PARTIAL_ALIVE = 1
    UNKNOWN = 2
    UNSUPPORTED = 3
    BLOCKED = 4
    BUILD_BROKEN = 5


def compose_standing(values: tuple[Standing, ...]) -> Standing:
    if not values:
        return Standing.UNKNOWN
    return max(values)
