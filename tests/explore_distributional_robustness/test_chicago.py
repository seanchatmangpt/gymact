from fractions import Fraction

from gymact.explore_distributional_robustness import Calibration, Candidate, Selector, Standing, qualify


def test_bounded_robustness_receipts_without_actuation() -> None:
    candidates = (
        Candidate("nominal", Fraction(1, 10), Fraction(4, 10), Fraction(1, 10), Fraction(9, 10)),
        Candidate("robust", Fraction(2, 10), Fraction(3, 10), Fraction(2, 10), Fraction(8, 10)),
    )
    calibration = Calibration(3, "cal-v3", 100, Fraction(1, 20), Fraction(1, 4))
    result = qualify("seanchatmangpt/gymact@" + "a" * 40 + "#semantic", candidates, Selector.MIN_WORST, calibration, Fraction(1, 3))
    assert result.selected.name == "robust"
    assert result.standing is Standing.PARTIAL_ALIVE
    assert result.receipt is not None and result.receipt.replay()
    assert result.receipt.body.actuation_performed is False


def test_broken_dependency_suppresses_receipt() -> None:
    candidate = Candidate("x", Fraction(1, 10), Fraction(1, 10), Fraction(1, 10), Fraction(1, 1))
    calibration = Calibration(1, "cal", 10, Fraction(0), Fraction(1, 10))
    result = qualify("subject", (candidate,), Selector.MIN_WORST, calibration, Fraction(1, 2), dependency_broken=True)
    assert result.standing is Standing.BUILD_BROKEN
    assert result.receipt is None
