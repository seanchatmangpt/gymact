from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality.independent_checker import independent_gap
from gymact.explore_kantorovich_duality.potentials import DualPotentials
from gymact.explore_kantorovich_duality.primal import PrimalPlan


def test_independent_gap_zero() -> None:
    plan = PrimalPlan((("a", "b", Fraction(1)),))
    potentials = DualPotentials({"a": Fraction(1)}, {"b": Fraction(2)})
    assert independent_gap(
        plan,
        potentials,
        {("a", "b"): Fraction(3)},
        {"a": Fraction(1)},
        {"b": Fraction(1)},
    ) == 0


def test_weak_duality_violation_refuses() -> None:
    plan = PrimalPlan((("a", "b", Fraction(1)),))
    potentials = DualPotentials({"a": Fraction(2)}, {"b": Fraction(2)})
    with pytest.raises(ValueError, match="WEAK_DUALITY_VIOLATION"):
        independent_gap(
            plan,
            potentials,
            {("a", "b"): Fraction(3)},
            {"a": Fraction(1)},
            {"b": Fraction(1)},
        )
