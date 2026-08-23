from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality import DualityRefusal, FiniteMeasure, GroundMetric, TransportPlan


def _metric() -> GroundMetric:
    return GroundMetric.admit({"a", "b"}, {("a", "b"): 1, ("b", "a"): 1})


def test_metric_and_plan_mass_conservation() -> None:
    source = FiniteMeasure.normalize({"a": 1, "b": 1})
    target = FiniteMeasure.normalize({"a": 1, "b": 1})
    plan = TransportPlan({("a", "a"): Fraction(1, 2), ("b", "b"): Fraction(1, 2)})
    assert plan.admit(source, target) is plan
    assert _metric()("a", "b") == 1


def test_negative_flow_refuses() -> None:
    source = FiniteMeasure.normalize({"a": 1})
    with pytest.raises(DualityRefusal, match="NEGATIVE_FLOW"):
        TransportPlan({("a", "a"): Fraction(-1)}).admit(source, source)
