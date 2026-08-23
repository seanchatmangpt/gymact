from gymact.explore_decision_realization import CalibrationPoint, Decision, DecisionIdentity, REQUIRED, Standing, Subject, calibrate, canonical_worlds, qualify, replay


def test_chicago_realized_decision_caps_positive_standing_and_preserves_failure() -> None:
    subject = Subject.parse("seanchatmangpt/gymact", "f" * 40, "1" * 64)
    decision = DecisionIdentity(subject, "decision-1", "risk", 3, "2" * 64, Decision.DEFER, 100, 0.2)
    calibration = calibrate(3, "3" * 64, [CalibrationPoint(Decision.DEFER, 0.2, value) for value in (0.15, 0.2, 0.25, 0.3)])
    good = qualify(decision, calibration, "ROBUST_DEFER", set(REQUIRED), (Standing.ALIVE, Standing.PARTIAL_ALIVE))
    assert good.standing is Standing.PARTIAL_ALIVE
    assert good.receipt is not None
    assert replay(good.receipt, good.receipt.digest()) == "REPLAY_MATCH"
    assert not good.receipt.actuation_performed
    broken = qualify(decision, calibration, "ROBUST_DEFER", set(REQUIRED), (Standing.ALIVE, Standing.BUILD_BROKEN))
    assert broken.standing is Standing.BUILD_BROKEN
    assert broken.receipt is None
    worlds = canonical_worlds()
    assert len(worlds) == 7
    assert any(world.dependency_standing is Standing.BUILD_BROKEN for world in worlds)
