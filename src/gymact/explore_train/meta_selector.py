from dataclasses import dataclass


@dataclass(frozen=True)
class SelectionEvidence:
    name: str
    correctness: float
    reversibility: float
    cost: float


def choose(items: tuple[SelectionEvidence, ...]) -> SelectionEvidence:
    if not items:
        raise ValueError("REFUSED_EMPTY_SELECTION")
    return max(
        items,
        key=lambda item: (
            item.correctness * 3 + item.reversibility * 2 - item.cost,
            item.name,
        ),
    )
