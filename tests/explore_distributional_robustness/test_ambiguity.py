from fractions import Fraction

import pytest

from gymact.explore_distributional_robustness import AmbiguityKind, AmbiguitySet, FiniteDistribution, chi_square


def test_tv_membership_is_radius_bounded() -> None:
    center = FiniteDistribution.from_mapping({"a": 1, "b": 1})
    candidate = FiniteDistribution.from_mapping({"a": 3, "b": 1})
    assert AmbiguitySet(center, AmbiguityKind.TV, Fraction(1, 4)).admits_tv(candidate)
    assert not AmbiguitySet(center, AmbiguityKind.TV, Fraction(1, 8)).admits_tv(candidate)


def test_chi_square_refuses_new_support() -> None:
    center = FiniteDistribution.from_mapping({"a": 1, "b": 1})
    candidate = FiniteDistribution.from_mapping({"a": 1, "c": 1})
    with pytest.raises(ValueError, match="POSITIVITY_VIOLATION"):
        chi_square(candidate, center)
