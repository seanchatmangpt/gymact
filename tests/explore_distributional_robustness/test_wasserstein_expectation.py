from fractions import Fraction

from gymact.explore_distributional_robustness import FiniteDistribution, wasserstein_1, worst_case_expectation


def test_wasserstein_and_worst_case_are_explicitly_distinct() -> None:
    center = FiniteDistribution.from_mapping({"safe": 3, "fail": 1})
    shifted = FiniteDistribution.from_mapping({"safe": 1, "fail": 3})
    assert wasserstein_1(center, shifted, {("fail", "safe"): 2}) == 1
    risk, witness = worst_case_expectation((center, shifted), {"safe": 0, "fail": 4})
    assert risk == 3
    assert witness == shifted
