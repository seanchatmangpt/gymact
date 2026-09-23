from __future__ import annotations

from fractions import Fraction

from .distribution import FiniteDistribution


def total_variation(left: FiniteDistribution, right: FiniteDistribution) -> Fraction:
    lhs = left.as_dict()
    rhs = right.as_dict()
    keys = lhs.keys() | rhs.keys()
    total = sum((abs(lhs.get(k, Fraction(0)) - rhs.get(k, Fraction(0))) for k in keys), Fraction(0))
    return total / 2


def overlap(left: FiniteDistribution, right: FiniteDistribution) -> Fraction:
    lhs = left.as_dict()
    rhs = right.as_dict()
    keys = lhs.keys() | rhs.keys()
    return sum((min(lhs.get(k, Fraction(0)), rhs.get(k, Fraction(0))) for k in keys), Fraction(0))


def assert_tv_overlap_identity(left: FiniteDistribution, right: FiniteDistribution) -> None:
    assert total_variation(left, right) + overlap(left, right) == 1
