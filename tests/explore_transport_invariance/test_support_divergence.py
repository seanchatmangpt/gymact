from fractions import Fraction

import pytest

from gymact.explore_transport_invariance import Cell, Refusal, assess_support, overlap_coefficient, total_variation


def test_support_and_tv_are_exact() -> None:
    cells = (Cell("a", Fraction(3, 4), Fraction(1, 2)), Cell("b", Fraction(1, 4), Fraction(1, 2)))
    assert assess_support(cells).overlap == Fraction(3, 4)
    assert total_variation(cells) == Fraction(1, 4)
    assert overlap_coefficient(cells) == Fraction(3, 4)


def test_missing_source_support_refuses() -> None:
    with pytest.raises(Refusal):
        assess_support((Cell("a", Fraction(0), Fraction(1)),))
