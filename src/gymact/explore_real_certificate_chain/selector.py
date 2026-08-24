from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    name: str
    independence: int
    runtime_diversity: int
    cost: int


def select(candidates: list[Candidate], strategy: str) -> Candidate:
    if not candidates:
        raise ValueError("METHOD_MISMATCH")
    keys = {
        "independence": lambda c: (-c.independence, c.cost, c.name),
        "runtime": lambda c: (-c.runtime_diversity, c.cost, c.name),
        "cost": lambda c: (c.cost, -c.independence, c.name),
    }
    if strategy not in keys:
        raise ValueError("METHOD_MISMATCH")
    return min(candidates, key=keys[strategy])
