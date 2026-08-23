from __future__ import annotations

from fractions import Fraction

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.potential import DualPotential


def dual_value(potential: DualPotential, source: FiniteMeasure, target: FiniteMeasure) -> Fraction:
    source_term = sum((source.mass[x] * potential.u[x] for x in source.mass), Fraction(0))
    target_term = sum((target.mass[y] * potential.v[y] for y in target.mass), Fraction(0))
    return source_term + target_term
