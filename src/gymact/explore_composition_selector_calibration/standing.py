from enum import Enum
class Standing(str,Enum):
    UNKNOWN='UNKNOWN'; PARTIAL_ALIVE='PARTIAL_ALIVE'; BUILD_BROKEN='BUILD_BROKEN'
def combine(states:tuple[Standing,...])->Standing:
    if Standing.BUILD_BROKEN in states:return Standing.BUILD_BROKEN
    if states and all(s is Standing.PARTIAL_ALIVE for s in states):return Standing.PARTIAL_ALIVE
    return Standing.UNKNOWN
