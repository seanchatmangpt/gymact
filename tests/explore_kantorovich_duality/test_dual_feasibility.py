from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality import DualPotential, DualityRefusal, GroundMetric


def test_dual_feasibility_and_reduced_costs() -> None:
    metric = GroundMetric.admit({"a", "b"}, {("a", "b"): 1, ("b", "a"): 1})
    potential = DualPotential({"a": Fraction(0), "b": Fraction(0)}, {"a": Fraction(0), "b": Fraction(0)})
    assert potential.admit({"a", "b"}, {"a", "b"}, metric) is potential


def test_infeasible_dual_refuses() -> None:
    metric = GroundMetric.admit({"a", "b"}, {("a", "b"): 1, ("b", "a"): 1})
    with pytest.raises(DualityRefusal, match="DUAL_INFEASIBLE"):
        DualPotential({"a": Fraction(2), "b": Fraction(0)}, {"a": Fraction(0), "b": Fraction(0)}).admit({"a", "b"}, {"a", "b"}, metric)
