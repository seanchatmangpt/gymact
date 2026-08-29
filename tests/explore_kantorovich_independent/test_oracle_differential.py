from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.plan import TransportPlan
from gymact.explore_kantorovich_independent.differential import compare
from gymact.explore_kantorovich_independent.oracle_bridge import admit_oracle_agreement
from gymact.explore_kantorovich_independent.primal_to_dual import construct_dual
from gymact.explore_kantorovich_independent.raw_verifier import verify
from gymact.explore_kantorovich_independent.refusal import IndependentVerifierRefusal


def test_dual_evidence_agrees_with_manufacturer_and_two_primal_oracles() -> None:
    points = {"a": 0, "b": 10, "c": 1, "d": 11}
    metric = GroundMetric.admit(set(points), {(x, y): abs(points[x] - points[y]) for x in points for y in points})
    source = FiniteMeasure.normalize({"a": 1, "b": 1})
    target = FiniteMeasure.normalize({"c": 1, "d": 1})
    plan = TransportPlan({("a", "c"): Fraction(1, 2), ("b", "d"): Fraction(1, 2)})
    potential = construct_dual(plan, source, target, metric)
    witness = verify(plan, potential, source, target, metric)
    delta = compare(plan, potential, source, target, metric)
    agreement = admit_oracle_agreement(Fraction(1), Fraction(1), witness)
    assert delta.manufacturer_primal == delta.independent_dual == Fraction(1)
    assert agreement.primary == agreement.exhaustive == agreement.dual
    with pytest.raises(IndependentVerifierRefusal, match="PRIMAL_ORACLE_DIVERGENCE"):
        admit_oracle_agreement(Fraction(1), Fraction(2), witness)
