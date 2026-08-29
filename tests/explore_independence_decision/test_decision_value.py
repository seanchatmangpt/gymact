from fractions import Fraction

from gymact.explore_independence_decision import (
    Candidate,
    InformationOption,
    LossMatrix,
    Strategy,
    best_option,
    decide,
    select,
)


def test_asymmetric_loss_can_prefer_defer() -> None:
    loss = LossMatrix(
        false_independent=Fraction(10),
        false_dependent=Fraction(1),
        defer=Fraction(1, 2),
    )
    result = decide(Fraction(4, 5), loss)
    assert result.decision.value == "DEFER"


def test_information_value_and_selector_plurality() -> None:
    inspect = InformationOption("inspect-roots", Fraction(3, 4), Fraction(1, 4))
    rerun = InformationOption("rerun-oracle", Fraction(1, 2), Fraction(1, 3))
    assert best_option((inspect, rerun)) == inspect
    a = Candidate("a", Fraction(1, 5), Fraction(1, 20), Fraction(1, 4), Fraction(1, 10))
    b = Candidate("b", Fraction(1, 4), Fraction(0), Fraction(3, 4), Fraction(1, 3))
    assert select((a, b), Strategy.MIN_EXPECTED_LOSS) == a
    assert select((a, b), Strategy.MAX_INFORMATION_VALUE) == b
