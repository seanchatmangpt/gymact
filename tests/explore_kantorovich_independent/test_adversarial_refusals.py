from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.plan import TransportPlan
from gymact.explore_kantorovich_duality.potential import DualPotential
from gymact.explore_kantorovich_independent.primal_to_dual import construct_dual
from gymact.explore_kantorovich_independent.raw_verifier import verify
from gymact.explore_kantorovich_independent.refusal import IndependentVerifierRefusal


def world():
    points = {"a": 0, "b": 10, "c": 1, "d": 11}
    metric = GroundMetric.admit(set(points), {(x, y): abs(points[x] - points[y]) for x in points for y in points})
    return FiniteMeasure.normalize({"a": 1, "b": 1}), FiniteMeasure.normalize({"c": 1, "d": 1}), metric


def test_nonoptimal_crossed_plan_cannot_manufacture_a_dual_certificate() -> None:
    source, target, metric = world()
    crossed = TransportPlan({("a", "d"): Fraction(1, 2), ("b", "c"): Fraction(1, 2)})
    with pytest.raises(IndependentVerifierRefusal) as error:
        construct_dual(crossed, source, target, metric)
    assert error.value.code in {"DUAL_OFFSET_NEGATIVE_CYCLE", "INTRA_COMPONENT_DUAL_INFEASIBLE"}


def test_infeasible_dual_is_refused_before_strong_duality_claim() -> None:
    source, target, metric = world()
    plan = TransportPlan({("a", "c"): Fraction(1, 2), ("b", "d"): Fraction(1, 2)})
    bad = DualPotential({"a": Fraction(100), "b": Fraction(0)}, {"c": Fraction(1), "d": Fraction(1)})
    with pytest.raises(IndependentVerifierRefusal) as error:
        verify(plan, bad, source, target, metric)
    assert error.value.code == "DUAL_INFEASIBLE"
