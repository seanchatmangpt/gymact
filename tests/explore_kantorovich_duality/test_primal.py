from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality.primal import PrimalPlan


def test_primal_cost_exact() -> None:
    plan = PrimalPlan((("a", "b", Fraction(1, 2)),))
    assert plan.cost({("a", "b"): Fraction(4)}) == 2


def test_missing_ground_cost_refuses() -> None:
    plan = PrimalPlan((("a", "b", Fraction(1)),))
    with pytest.raises(ValueError, match="MISSING_GROUND_COST"):
        plan.cost({})
