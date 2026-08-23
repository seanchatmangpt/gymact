from __future__ import annotations

from fractions import Fraction

from .measure import FiniteMeasure
from .potential import DualPotential


def dual_value(potential: DualPotential, source: FiniteMeasure, target: FiniteMeasure) -> Fraction:
    left = sum((source.mass[x] * potential.u[x] for x in source.mass), Fraction(0))
    right = sum((target.mass[y] * potential.v[y] for y in target.mass), Fraction(0))
    return left + right
