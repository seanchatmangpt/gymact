from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality.dual_feasibility import assert_dual_feasible
from gymact.explore_kantorovich_duality.potentials import DualPotentials


def test_negative_reduced_cost_refuses() -> None:
    potentials = DualPotentials({"a": Fraction(2)}, {"b": Fraction(2)})
    with pytest.raises(ValueError, match="DUAL_INFEASIBLE"):
        assert_dual_feasible(potentials, {("a", "b"): Fraction(3)})
