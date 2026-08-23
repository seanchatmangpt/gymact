from fractions import Fraction

from gymact.explore_kantorovich_duality.certificate import DualityCertificate
from gymact.explore_kantorovich_duality.potentials import DualPotentials
from gymact.explore_kantorovich_duality.primal import PrimalPlan
from gymact.explore_kantorovich_duality.qualification import qualify
from gymact.explore_kantorovich_duality.standing import Standing


def fixtures():
    plan = PrimalPlan((("a", "b", Fraction(1)),))
    potentials = DualPotentials({"a": Fraction(1)}, {"b": Fraction(2)})
    metric = {("a", "b"): Fraction(3)}
    supply = {"a": Fraction(1)}
    demand = {"b": Fraction(1)}
    return plan, potentials, metric, supply, demand


def test_zero_gap_can_issue_bounded_receipt() -> None:
    plan, potentials, metric, supply, demand = fixtures()
    receipt = qualify(
        "subject",
        DualityCertificate(Fraction(3), 1, 1),
        plan,
        potentials,
        metric,
        supply,
        demand,
        [Standing.ALIVE],
    )
    assert receipt is not None
    assert receipt.standing is Standing.PARTIAL_ALIVE


def test_build_broken_suppresses_receipt() -> None:
    plan, potentials, metric, supply, demand = fixtures()
    assert qualify(
        "subject",
        DualityCertificate(Fraction(3), 1, 1),
        plan,
        potentials,
        metric,
        supply,
        demand,
        [Standing.BUILD_BROKEN],
    ) is None
