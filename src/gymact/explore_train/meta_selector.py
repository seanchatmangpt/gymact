from dataclasses import dataclass

@dataclass(frozen=True)
class SelectionEvidence:
    name: str
    correctness: float
    reversibility: float
    cost: float


def choose(items: tuple[SelectionEvidence, ...]) -> SelectionEvidence:
    if not items: raise ValueError("REFUSED_EMPTY_SELECTION")
    return max(items, key=lambda i: (i.correctness * 3 + i.reversibility * 2 - i.cost, i.name))
