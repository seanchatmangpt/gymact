from enum import IntEnum

class Standing(IntEnum):
    ALIVE = 0
    PARTIAL_ALIVE = 1
    UNKNOWN = 2
    UNSUPPORTED = 3
    BUILD_BROKEN = 4

def compose(*states: Standing) -> Standing:
    return max(states, default=Standing.UNKNOWN)
