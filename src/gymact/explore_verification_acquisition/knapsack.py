from dataclasses import dataclass

from .budget import AcquisitionBudget
from .capability import RailCapability
from .dependence import IndependenceProof, independent_set
from .strategies import Score


@dataclass(frozen=True, slots=True)
class Selection:
    rails: tuple[RailCapability, ...]
    total_score: float


def select_exact(
    rails: tuple[RailCapability, ...],
    scores: dict[str, Score],
    budget: AcquisitionBudget,
    proofs: tuple[IndependenceProof, ...] = (),
) -> Selection:
    best = Selection((), 0.0)
    count = len(rails)
    for mask in range(1, 1 << count):
        chosen = tuple(rails[index] for index in range(count) if mask & (1 << index))
        if not budget.admits(chosen) or not independent_set(chosen, proofs):
            continue
        value = sum(scores[rail.fingerprint].value for rail in chosen)
        candidate_key = (value, tuple(rail.rail_id for rail in chosen))
        best_key = (best.total_score, tuple(rail.rail_id for rail in best.rails))
        if candidate_key > best_key:
            best = Selection(chosen, value)
    return best
