from fractions import Fraction

from gymact.explore_independence_decision import Cusum, DependenceEvidence, EvidenceRootSet


def test_shared_root_blocks_independence_even_with_zero_empirical_dependence() -> None:
    left = EvidenceRootSet(frozenset({"a", "shared"}))
    right = EvidenceRootSet(frozenset({"b", "shared"}))
    overlap, union = left.jaccard(right)
    dependence = DependenceEvidence(Fraction(overlap, union), Fraction(0), Fraction(0), 50)
    assert dependence.empirically_independent
    assert not dependence.structurally_independent
    assert not dependence.independence_admissible


def test_cusum_detects_dependence_drift() -> None:
    detector = Cusum(reference=Fraction(1, 10), threshold=Fraction(1, 2))
    index, score = detector.scan((Fraction(0), Fraction(1, 10), Fraction(2, 5), Fraction(1, 2)))
    assert index == 3
    assert score >= Fraction(1, 2)
