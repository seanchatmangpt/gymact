from fractions import Fraction

from gymact.explore_kantorovich_duality import DualPotential, FiniteMeasure, GroundMetric, TransportPlan, certify


def test_exact_strong_duality_certificate() -> None:
    source = FiniteMeasure.normalize({"a": 1})
    target = FiniteMeasure.normalize({"b": 1})
    metric = GroundMetric.admit({"a", "b"}, {("a", "b"): 1, ("b", "a"): 1})
    plan = TransportPlan({("a", "b"): Fraction(1)})
    potential = DualPotential({"a": Fraction(1)}, {"b": Fraction(0)})
    cert = certify(plan, potential, source, target, metric)
    assert cert.primal == cert.dual == 1
    assert cert.gap == 0
