from __future__ import annotations

from fractions import Fraction
from typing import Iterable, Mapping

from .distribution import FiniteDistribution
from .refusals import refuse


def expectation(distribution: FiniteDistribution, loss: Mapping[str, Fraction | int]) -> Fraction:
    return sum((mass * Fraction(loss[key]) for key, mass in distribution.mass), Fraction(0))


def worst_case_expectation(
    candidates: Iterable[FiniteDistribution],
    loss: Mapping[str, Fraction | int],
) -> tuple[Fraction, FiniteDistribution]:
    materialized = tuple(candidates)
    if not materialized:
        raise refuse("EMPTY_AMBIGUITY_SET", "at least one admitted candidate is required")
    scored = tuple((expectation(candidate, loss), candidate) for candidate in materialized)
    return max(scored, key=lambda pair: (pair[0], pair[1].mass))
