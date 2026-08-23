import pytest

from gymact.explore_decision_realization import ActionClass, CUSUMState, CalibrationPoint, Decision, DecisionIdentity, Refused, Standing, Subject, admit, calibrate, current_calibration, manufacture, replay, update


def test_currentness_drift_authority_and_replay() -> None:
    calibration = calibrate(2, "a" * 64, [CalibrationPoint(Decision.INDEPENDENT, 0.2, value) for value in (0.1, 0.2, 0.25, 0.3)])
    assert calibration.admitted
    divergent = calibrate(2, "b" * 64, [CalibrationPoint(Decision.DEFER, 0.2, 0.2)] * 4)
    with pytest.raises(Refused, match="DIVERGENT_CURRENT_REALIZATION_CALIBRATION"):
        current_calibration((calibration, divergent))
    state, drifted = update(CUSUMState(), observed_loss=0.8, target_loss=0.2, slack=0.1, threshold=0.5)
    assert state.positive == pytest.approx(0.5) and drifted
    with pytest.raises(Refused, match="UNRECEIPTED_ACTUATION"):
        admit(ActionClass.DO)
    assert admit(ActionClass.DO, "BRCE") is ActionClass.DO
    subject = Subject.parse("seanchatmangpt/gymact", "c" * 40, "d" * 64)
    decision = DecisionIdentity(subject, "d", "p", 2, "e" * 64, Decision.DEFER, 1, 0.2)
    receipt = manufacture(decision, "ROBUST_DEFER", Standing.PARTIAL_ALIVE, 2)
    assert replay(receipt, receipt.digest()) == "REPLAY_MATCH"
    with pytest.raises(Refused, match="RECEIPT_DRIFT"):
        replay(receipt, "0" * 64)
