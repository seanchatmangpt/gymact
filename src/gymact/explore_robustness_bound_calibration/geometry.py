from __future__ import annotations

from fractions import Fraction

from .bound import RobustnessBound


def intersection_width(a: RobustnessBound, b: RobustnessBound) -> Fraction:
    return max(Fraction(0), min(a.upper, b.upper) - max(a.lower, b.lower))


def union_width(a: RobustnessBound, b: RobustnessBound) -> Fraction:
    return max(a.upper, b.upper) - min(a.lower, b.lower)


def interval_iou(a: RobustnessBound, b: RobustnessBound) -> Fraction:
    union = union_width(a, b)
    return Fraction(1) if union == 0 else intersection_width(a, b) / union


def identification_value(bound: RobustnessBound, domain_width: Fraction) -> Fraction:
    if domain_width <= 0:
        raise ValueError("domain_width must be positive")
    return max(Fraction(0), Fraction(1) - bound.width / domain_width)
