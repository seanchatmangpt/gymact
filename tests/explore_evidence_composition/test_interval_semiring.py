from gymact.explore_evidence_composition.interval import Interval
from gymact.explore_evidence_composition.semiring import EvidenceWeight


def test_unknown_dependence_is_more_conservative_than_independence() -> None:
    left = EvidenceWeight(Interval(0.7, 0.9), 2.0)
    right = EvidenceWeight(Interval(0.8, 0.95), 3.0)
    conservative = left.series(right)
    independent = left.series(right, independent=True)
    assert conservative.confidence.lower == 0.5
    assert independent.confidence.lower == 0.56
    assert conservative.cost == independent.cost == 5.0


def test_parallel_route_does_not_sum_confidence() -> None:
    first = EvidenceWeight(Interval(0.5, 0.7), 5.0, frozenset({"tls"}))
    second = EvidenceWeight(Interval(0.6, 0.8), 2.0, frozenset({"runtime"}))
    result = first.parallel(second)
    assert result.confidence == Interval(0.6, 0.8)
    assert result.blockers == frozenset()
