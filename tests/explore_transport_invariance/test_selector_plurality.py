from fractions import Fraction

from gymact.explore_transport_invariance import Candidate, select


def test_selector_families_can_disagree() -> None:
    low_risk = Candidate("low-risk", Fraction(1, 10), Fraction(1, 2), Fraction(1, 4), Fraction(2))
    high_support = Candidate("high-support", Fraction(1, 5), Fraction(9, 10), Fraction(1, 10), Fraction(4))
    candidates = (low_risk, high_support)
    assert select(candidates, "MIN_RISK").name == "low-risk"
    assert select(candidates, "MAX_SUPPORT").name == "high-support"
    assert select(candidates, "MAX_ESS").name == "high-support"
