from fractions import Fraction

from gymact.explore_kantorovich_duality.certificate import certify
from gymact.explore_kantorovich_duality.potentials import DualPotentials
from gymact.explore_kantorovich_duality.primal import PrimalPlan


def test_exact_certificate() -> None:
    plan = PrimalPlan((("a", "b", Fraction(1)),))
    potentials = DualPotentials({"a": Fraction(1)}, {"b": Fraction(2)})
    certificate = certify(
        plan,
        potentials,
        {("a", "b"): Fraction(3)},
        {"a": Fraction(1)},
        {"b": Fraction(1)},
    )
    assert certificate.optimum == 3
    assert certificate.positive_flows == 1
