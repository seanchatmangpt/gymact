from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality import DualPotential, DualityRefusal, GroundMetric, TransportPlan
from gymact.explore_kantorovich_duality.complementarity import admit_complementary_slackness


def test_positive_flow_requires_zero_reduced_cost() -> None:
    metric = GroundMetric.admit({"a", "b"}, {("a", "b"): 1, ("b", "a"): 1})
    plan = TransportPlan({("a", "b"): Fraction(1)})
    bad = DualPotential({"a": Fraction(0)}, {"b": Fraction(0)})
    with pytest.raises(DualityRefusal, match="COMPLEMENTARY_SLACKNESS_VIOLATION"):
        admit_complementary_slackness(plan, bad, metric)
