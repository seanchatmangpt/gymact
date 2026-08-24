from dataclasses import dataclass

from .refusal import FederationRefusal


@dataclass(frozen=True)
class PowlModel:
    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.nodes or len(set(self.nodes)) != len(self.nodes):
            raise FederationRefusal("INVALID_POWL_MODEL")
        known = set(self.nodes)
        if any(a not in known or b not in known for a, b in self.edges):
            raise FederationRefusal("POWL_UNKNOWN_NODE")


def bounded_reachable(model: PowlModel, start: str, goal: str, steps: int) -> bool:
    if steps < 0 or start not in model.nodes or goal not in model.nodes:
        raise FederationRefusal("INVALID_POWL_QUERY")
    frontier = {start}
    if start == goal:
        return True
    for _ in range(steps):
        frontier = {b for a, b in model.edges if a in frontier}
        if goal in frontier:
            return True
    return False
