from __future__ import annotations

from fractions import Fraction

from .distribution import FiniteDistribution


def total_variation(left: FiniteDistribution, right: FiniteDistribution) -> Fraction:
    l = left.as_dict()
    r = right.as_dict()
    keys = l.keys() | r.keys()
    return sum((abs(l.get(k, Fraction(0)) - r.get(k, Fraction(0))) for k in keys), Fraction(0)) / 2


def overlap(left: FiniteDistribution, right: FiniteDistribution) -> Fraction:
    l = left.as_dict()
    r = right.as_dict()
    keys = l.keys() | r.keys()
    return sum((min(l.get(k, Fraction(0)), r.get(k, Fraction(0))) for k in keys), Fraction(0))


def assert_tv_overlap_identity(left: FiniteDistribution, right: FiniteDistribution) -> None:
    assert total_variation(left, right) + overlap(left, right) == 1
