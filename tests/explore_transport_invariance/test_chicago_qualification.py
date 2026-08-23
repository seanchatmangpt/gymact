from fractions import Fraction

from gymact.explore_transport_invariance import Calibration, Candidate, Subject, issue, qualify, replay


def test_stressed_transport_stays_bounded_and_non_actuating() -> None:
    subject = Subject("seanchatmangpt/gymact", "d" * 40, "semantic-digest-0003")
    candidate = Candidate("robust", Fraction(1, 10), Fraction(9, 10), Fraction(1, 10), Fraction(4))
    calibration = Calibration(50, Fraction(1, 20), 3, "calibration-digest-003")
    result = qualify(candidate, calibration, (Fraction(1, 10), Fraction(3, 20)), Fraction(1, 5))
    assert result.standing == "PARTIAL_ALIVE"
    receipt = issue(subject, "MINIMAX", result.standing)
    assert receipt.actuation_performed is False
    assert replay(receipt)


def test_excess_stress_cannot_be_laundered_into_partial_alive() -> None:
    candidate = Candidate("fragile", Fraction(1, 10), Fraction(9, 10), Fraction(1, 10), Fraction(4))
    calibration = Calibration(50, Fraction(1, 20), 3, "calibration-digest-004")
    result = qualify(candidate, calibration, (Fraction(2, 5),), Fraction(1, 5))
    assert result.standing == "UNSUPPORTED"
