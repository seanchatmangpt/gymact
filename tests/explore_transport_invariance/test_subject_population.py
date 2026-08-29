from fractions import Fraction

import pytest

from gymact.explore_transport_invariance import Cell, Refusal, Subject, normalize


def test_exact_subject_and_population_normalization() -> None:
    subject = Subject("seanchatmangpt/gymact", "b" * 40, "semantic-digest-0001")
    assert subject.identity.startswith("seanchatmangpt/gymact@")
    cells = normalize((Cell("a", Fraction(2), Fraction(1)), Cell("b", Fraction(2), Fraction(3))))
    assert sum(c.source_mass for c in cells) == 1
    assert sum(c.target_mass for c in cells) == 1


def test_short_sha_refuses() -> None:
    with pytest.raises(Refusal):
        Subject("seanchatmangpt/gymact", "abc", "semantic-digest-0001")
