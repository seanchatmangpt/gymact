from fractions import Fraction

import pytest

from gymact.explore_transport_invariance import Cell, Refusal, support_erosion
from gymact.explore_transport_invariance.perturbation import apply


def test_support_erosion_is_reversible_evidence() -> None:
    cells = (Cell("a", Fraction(1, 2), Fraction(1, 2)), Cell("b", Fraction(1, 2), Fraction(1, 2)))
    stressed = apply(cells, support_erosion("a", Fraction(1, 4)).perturbations)
    assert stressed[0].source_mass == Fraction(1, 4)


def test_negative_mass_refuses() -> None:
    cells = (Cell("a", Fraction(1, 4), Fraction(1)),)
    with pytest.raises(Refusal):
        apply(cells, support_erosion("a", Fraction(1, 2)).perturbations)
