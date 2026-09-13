from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality.mass_balance import assert_mass_balance
from gymact.explore_kantorovich_duality.primal import PrimalPlan


def test_mass_balance_passes() -> None:
    plan = PrimalPlan((("a", "b", Fraction(1)),))
    assert_mass_balance(plan, {"a": Fraction(1)}, {"b": Fraction(1)})


def test_mass_balance_refuses_loss() -> None:
    plan = PrimalPlan((("a", "b", Fraction(1, 2)),))
    with pytest.raises(ValueError, match="MASS_BALANCE"):
        assert_mass_balance(plan, {"a": Fraction(1)}, {"b": Fraction(1)})
