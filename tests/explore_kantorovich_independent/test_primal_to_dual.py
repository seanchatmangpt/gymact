from fractions import Fraction

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.plan import TransportPlan
from gymact.explore_kantorovich_independent.primal_to_dual import construct_dual
from gymact.explore_kantorovich_independent.raw_verifier import verify


def test_optimal_disconnected_support_recovers_dual_by_component_offsets() -> None:
    points = {"a": 0, "b": 10, "c": 1, "d": 11}
    metric = GroundMetric.admit(set(points), {(x, y): abs(points[x] - points[y]) for x in points for y in points})
    source = FiniteMeasure.normalize({"a": 1, "b": 1})
    target = FiniteMeasure.normalize({"c": 1, "d": 1})
    plan = TransportPlan({("a", "c"): Fraction(1, 2), ("b", "d"): Fraction(1, 2)})
    potential = construct_dual(plan, source, target, metric)
    witness = verify(plan, potential, source, target, metric)
    assert potential.u[min(potential.u)] == 0
    assert witness.optimal
    assert witness.primal == Fraction(1)
