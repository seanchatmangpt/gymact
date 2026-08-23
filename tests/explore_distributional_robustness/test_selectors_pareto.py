from fractions import Fraction

from gymact.explore_distributional_robustness import Candidate, Selector, frontier, select


def _candidates() -> tuple[Candidate, ...]:
    return (
        Candidate("nominal", Fraction(1, 10), Fraction(4, 10), Fraction(2, 10), Fraction(9, 10)),
        Candidate("robust", Fraction(2, 10), Fraction(3, 10), Fraction(3, 10), Fraction(8, 10)),
        Candidate("support", Fraction(3, 10), Fraction(5, 10), Fraction(1, 10), Fraction(10, 10)),
    )


def test_selectors_disagree_lawfully() -> None:
    candidates = _candidates()
    assert select(candidates, Selector.MIN_NOMINAL).name == "nominal"
    assert select(candidates, Selector.MIN_WORST).name == "robust"
    assert select(candidates, Selector.MAX_SUPPORT).name == "support"


def test_pareto_preserves_incomparable_candidates() -> None:
    assert {c.name for c in frontier(_candidates())} == {"nominal", "robust", "support"}
