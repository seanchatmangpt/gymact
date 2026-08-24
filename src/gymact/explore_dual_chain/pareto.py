from dataclasses import dataclass

@dataclass(frozen=True)
class Candidate:
    name: str
    independence: int
    runtime_diversity: int
    cost: int

def frontier(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    def dominates(a: Candidate, b: Candidate) -> bool:
        weak = a.independence >= b.independence and a.runtime_diversity >= b.runtime_diversity and a.cost <= b.cost
        strict = (a.independence, a.runtime_diversity, -a.cost) != (b.independence, b.runtime_diversity, -b.cost)
        return weak and strict
    return tuple(c for c in candidates if not any(dominates(o, c) for o in candidates if o != c))
