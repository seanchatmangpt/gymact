from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from .strategies import OPEStrategy


@dataclass(frozen=True, slots=True)
class EvaluationVector:
    strategy: OPEStrategy
    estimate: Fraction
    support_ratio: Fraction
    effective_sample_ratio: Fraction
    max_weight: Fraction
    shift: Fraction


def dominates(left: EvaluationVector, right: EvaluationVector) -> bool:
    not_worse = (
        left.support_ratio >= right.support_ratio
        and left.effective_sample_ratio >= right.effective_sample_ratio
        and left.max_weight <= right.max_weight
        and left.shift <= right.shift
    )
    strictly_better = (
        left.support_ratio > right.support_ratio
        or left.effective_sample_ratio > right.effective_sample_ratio
        or left.max_weight < right.max_weight
        or left.shift < right.shift
    )
    return not_worse and strictly_better


def frontier(vectors: Iterable[EvaluationVector]) -> tuple[EvaluationVector, ...]:
    rows = tuple(vectors)
    survivors = [
        candidate
        for candidate in rows
        if not any(dominates(other, candidate) for other in rows if other is not candidate)
    ]
    return tuple(sorted(survivors, key=lambda row: row.strategy.value))
