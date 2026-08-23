from fractions import Fraction

import pytest

from gymact.explore_kantorovich_duality.authority import ActionClass, admit
from gymact.explore_kantorovich_duality.certificate import certify
from gymact.explore_kantorovich_duality.potentials import DualPotentials
from gymact.explore_kantorovich_duality.primal import PrimalPlan
from gymact.explore_kantorovich_duality.qualification import qualify
from gymact.explore_kantorovich_duality.replay import replay
from gymact.explore_kantorovich_duality.standing import Standing
from gymact.explore_kantorovich_duality.subject import Subject


def test_primal_dual_chicago() -> None:
    subject = Subject("seanchatmangpt/gymact", "4" * 40, "kantorovich-duality")
    plan = PrimalPlan((("source", "target", Fraction(1)),))
    potentials = DualPotentials({"source": Fraction(1)}, {"target": Fraction(2)})
    metric = {("source", "target"): Fraction(3)}
    supply = {"source": Fraction(1)}
    demand = {"target": Fraction(1)}

    certificate = certify(plan, potentials, metric, supply, demand)
    receipt = qualify(
        subject.identity,
        certificate,
        plan,
        potentials,
        metric,
        supply,
        demand,
        [Standing.ALIVE],
    )
    assert receipt is not None
    assert receipt.standing is Standing.PARTIAL_ALIVE
    replay(receipt, receipt.digest())

    with pytest.raises(ValueError, match="UNRECEIPTED_ACTUATION"):
        admit(ActionClass.DO)

    assert qualify(
        subject.identity,
        certificate,
        plan,
        potentials,
        metric,
        supply,
        demand,
        [Standing.BUILD_BROKEN],
    ) is None
