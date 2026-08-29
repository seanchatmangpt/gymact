from fractions import Fraction

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.plan import TransportPlan
from gymact.explore_kantorovich_duality.potential import DualPotential
from gymact.explore_kantorovich_independent.engine_identity import INDEPENDENT_ENGINE, MANUFACTURER_ENGINE, admit_independent
from gymact.explore_kantorovich_independent.raw_verifier import verify


def metric() -> GroundMetric:
    points = {"a": 0, "b": 10, "c": 1, "d": 11}
    return GroundMetric.admit(set(points), {(x, y): abs(points[x] - points[y]) for x in points for y in points})


def test_raw_verifier_proves_exact_optimum_with_distinct_engine_identity() -> None:
    source = FiniteMeasure.normalize({"a": 1, "b": 1})
    target = FiniteMeasure.normalize({"c": 1, "d": 1})
    plan = TransportPlan({("a", "c"): Fraction(1, 2), ("b", "d"): Fraction(1, 2)})
    potential = DualPotential({"a": Fraction(0), "b": Fraction(0)}, {"c": Fraction(1), "d": Fraction(1)})
    admit_independent(INDEPENDENT_ENGINE, MANUFACTURER_ENGINE)
    witness = verify(plan, potential, source, target, metric())
    assert witness.primal == witness.dual == Fraction(1)
    assert witness.gap == 0
    assert witness.active_arcs == 2
