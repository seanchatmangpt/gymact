from fractions import Fraction

import pytest

from gymact.explore_independence_decision import (
    REQUIRED,
    ActionClass,
    DecisionCalibration,
    DependenceEvidence,
    LossMatrix,
    Refused,
    Standing,
    Strategy,
    Subject,
    admit,
    decide,
    qualify,
    replay,
    require_methodologies,
)


def test_chicago_exact_subject_decision_receipt_and_failure_dominance() -> None:
    subject = Subject.parse("seanchatmangpt/gymact", "c" * 40, "d" * 64)
    require_methodologies(REQUIRED)
    decision = decide(
        Fraction(9, 10),
        LossMatrix(false_independent=Fraction(1), false_dependent=Fraction(4), defer=Fraction(1)),
    )
    assert decision.decision.value == "INDEPENDENT"
    calibration = DecisionCalibration(100, 1, 2, 7, "cal-7")
    dependence = DependenceEvidence(Fraction(0), Fraction(0), Fraction(0), 100)
    qualified = qualify(
        subject_key=subject.key,
        strategy=Strategy.MIN_EXPECTED_LOSS.value,
        decision=decision,
        calibration=calibration,
        dependence=dependence,
        methodologies_closed=True,
        dependency_broken=False,
        exact_subject_executed=True,
    )
    assert qualified.standing is Standing.PARTIAL_ALIVE
    assert qualified.receipt is not None
    assert replay(qualified.receipt, qualified.receipt.digest()) == "REPLAY_MATCH"

    broken = qualify(
        subject_key=subject.key,
        strategy=Strategy.MIN_EXPECTED_LOSS.value,
        decision=decision,
        calibration=calibration,
        dependence=dependence,
        methodologies_closed=True,
        dependency_broken=True,
        exact_subject_executed=True,
    )
    assert broken.standing is Standing.BUILD_BROKEN
    assert broken.receipt is None

    with pytest.raises(Refused, match="UNRECEIPTED_ACTUATION"):
        admit(ActionClass.DO)
