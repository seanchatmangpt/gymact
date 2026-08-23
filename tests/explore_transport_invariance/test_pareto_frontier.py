from fractions import Fraction

from gymact.explore_transport_invariance import Candidate, frontier


def test_strict_dominance_only_removes_dominated_candidate() -> None:
    strong = Candidate("strong", Fraction(1, 10), Fraction(9, 10), Fraction(1, 10), Fraction(4))
    weak = Candidate("weak", Fraction(1, 5), Fraction(4, 5), Fraction(1, 5), Fraction(2))
    tradeoff = Candidate("tradeoff", Fraction(1, 20), Fraction(1, 2), Fraction(1, 4), Fraction(6))
    names = {c.name for c in frontier((strong, weak, tradeoff))}
    assert "weak" not in names
    assert names == {"strong", "tradeoff"}
