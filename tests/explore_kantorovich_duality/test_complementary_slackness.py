from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality.complementary_slackness import assert_complementary_slackness
from gymact.explore_kantorovich_duality.potentials import DualPotentials
from gymact.explore_kantorovich_duality.primal import PrimalPlan


def test_positive_flow_requires_zero_reduced_cost() -> None:
    plan = PrimalPlan((("a", "b", Fraction(1)),))
    potentials = DualPotentials({"a": Fraction(1)}, {"b": Fraction(1)})
    with pytest.raises(ValueError, match="COMPLEMENTARY_SLACKNESS"):
        assert_complementary_slackness(plan, potentials, {("a", "b"): Fraction(3)})
