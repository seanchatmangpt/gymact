from fractions import Fraction
from gymact.explore_validation_independence import Calibration, Candidate, CompositionMode, REQUIRED, Standing, Strategy, Subject, ValidationCase, qualify, replay

def test_independence_aware_chicago_caps_positive_and_preserves_red_failure():
    subject = Subject.parse("seanchatmangpt/gymact@" + "a"*40 + "#" + "b"*64)
    calibration = Calibration.from_cases(3, "d", (ValidationCase("a", Fraction(0), Fraction(1), Fraction(1,2)), ValidationCase("b", Fraction(0), Fraction(1), Fraction(1,2))))
    candidate = Candidate(CompositionMode.CONSERVATIVE, Fraction(1), Fraction(1,2), Fraction(0), Fraction(0), 1)
    good = qualify(subject, calibration, (candidate,), Strategy.MAX_COVERAGE, REQUIRED, (Standing.ALIVE,), ("e1","e2"))
    assert good.standing is Standing.PARTIAL_ALIVE
    assert good.receipt and replay(good.receipt, good.receipt.digest) == "REPLAY_MATCH"
    bad = qualify(subject, calibration, (candidate,), Strategy.MAX_COVERAGE, REQUIRED, (Standing.ALIVE, Standing.BUILD_BROKEN), ("e1",))
    assert bad.standing is Standing.BUILD_BROKEN and bad.receipt is None
