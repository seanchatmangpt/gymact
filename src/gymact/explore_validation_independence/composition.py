from enum import StrEnum

from .effective_independence import IndependenceScore
from .evidence import Evidence
from .interval import Interval
from .refusal import Refused


class CompositionMode(StrEnum):
    CONSERVATIVE = "CONSERVATIVE"
    INDEPENDENCE_QUALIFIED = "INDEPENDENCE_QUALIFIED"


def compose(
    left: Evidence,
    right: Evidence,
    mode: CompositionMode,
    score: IndependenceScore | None = None,
) -> Interval:
    if left.subject != right.subject:
        raise Refused("FOREIGN_SUBJECT_EVIDENCE")
    if mode is CompositionMode.CONSERVATIVE:
        return left.interval.frechet_and(right.interval)
    if score is None or score.effective < 1:
        raise Refused("INSUFFICIENT_EFFECTIVE_INDEPENDENCE")
    return left.interval.independent_and(right.interval)
