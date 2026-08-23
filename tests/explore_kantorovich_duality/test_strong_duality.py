from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality.potentials import DualPotentials
from gymact.explore_kantorovich_duality.primal import PrimalPlan
from gymact.explore_kantorovich_duality.strong_duality import assert_strong_duality


def test_strong_duality_exact() -> None:
    plan = PrimalPlan((("a", "b", Fraction(1)),))
    potentials = DualPotentials({"a": Fraction(1)}, {"b": Fraction(2)})
    assert assert_strong_duality(plan, potentials, {("a", "b"): Fraction(3)}, {"a": Fraction(1)}, {"b": Fraction(1)}) == 3


def test_gap_refuses() -> None:
    plan = PrimalPlan((("a", "b", Fraction(1)),))
    potentials = DualPotentials({"a": Fraction(1)}, {"b": Fraction(1)})
    with pytest.raises(ValueError, match="DUALITY_GAP"):
        assert_strong_duality(plan, potentials, {("a", "b"): Fraction(3)}, {"a": Fraction(1)}, {"b": Fraction(1)})
