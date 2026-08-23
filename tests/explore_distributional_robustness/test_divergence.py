from fractions import Fraction

from gymact.explore_distributional_robustness import FiniteDistribution, overlap, total_variation


def test_tv_overlap_identity() -> None:
    left = FiniteDistribution.from_mapping({"a": 3, "b": 1})
    right = FiniteDistribution.from_mapping({"a": 1, "b": 3})
    assert total_variation(left, right) == Fraction(1, 2)
    assert overlap(left, right) == Fraction(1, 2)
    assert total_variation(left, right) + overlap(left, right) == 1
