from fractions import Fraction

import pytest

from gymact.explore_distributional_robustness import FiniteDistribution, Subject


def test_subject_requires_exact_sha() -> None:
    with pytest.raises(ValueError, match="INVALID_SUBJECT"):
        Subject("seanchatmangpt/gymact", "abc", "semantic")


def test_distribution_normalizes_exactly() -> None:
    distribution = FiniteDistribution.from_mapping({"a": 1, "b": 3})
    assert distribution.as_dict() == {"a": Fraction(1, 4), "b": Fraction(3, 4)}


def test_zero_mass_refuses() -> None:
    with pytest.raises(ValueError, match="ZERO_TOTAL_MASS"):
        FiniteDistribution.from_mapping({"a": 0})
