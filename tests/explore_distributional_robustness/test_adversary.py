from fractions import Fraction

from gymact.explore_distributional_robustness import FiniteDistribution, total_variation, two_point_extremes


def test_two_point_adversary_preserves_center_and_radius() -> None:
    center = FiniteDistribution.from_mapping({"safe": 3, "fail": 1})
    worlds = two_point_extremes(center, Fraction(1, 4))
    assert center in worlds
    assert len(worlds) == 3
    assert all(total_variation(center, world) <= Fraction(1, 4) for world in worlds)
    assert worlds == two_point_extremes(center, Fraction(1, 4))
