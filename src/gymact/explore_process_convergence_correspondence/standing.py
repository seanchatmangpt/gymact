from enum import StrEnum
from .classifier import Direction
from .dependency import DependencyGraph
from .epoch import ClosureEpoch
from .obligation import State

class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    BLOCKED = "BLOCKED"
    BUILD_BROKEN = "BUILD_BROKEN"

def standing(epoch: ClosureEpoch, direction: Direction, graph: DependencyGraph | None = None) -> Standing:
    if any(o.state == State.FAIL for o in epoch.obligations):
        return Standing.BUILD_BROKEN
    if graph and graph.blocking_cut(epoch):
        return Standing.BLOCKED
    if direction in {Direction.OSCILLATING, Direction.REGRESSING, Direction.STALLED, Direction.UNKNOWN}:
        return Standing.UNKNOWN
    return Standing.PARTIAL_ALIVE
