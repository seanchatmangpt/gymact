from fractions import Fraction

import pytest

from gymact.explore_decision_transport.divergence import total_variation
from gymact.explore_decision_transport.population import Population
from gymact.explore_decision_transport.refusal import Refused
from gymact.explore_decision_transport.risk import transported_risk
from gymact.explore_decision_transport.support import support_overlap
from gymact.explore_decision_transport.weights import effective_sample_size, importance_weights


def test_shift_weights_and_risk_remain_distinct() -> None:
    source = Population.normalized({"a": Fraction(3), "b": Fraction(1)})
    target = Population.normalized({"a": Fraction(1), "b": Fraction(3)})
    assert total_variation(source, target) == Fraction(1, 2)
    assert support_overlap(source, target) == Fraction(1, 2)
    weights = importance_weights(source, target)
    sample_weights = [weights["a"], weights["b"]]
    assert effective_sample_size(sample_weights) < 2
    assert transported_risk([Fraction(0), Fraction(1)], sample_weights) == Fraction(9, 10)


def test_missing_target_support_refuses() -> None:
    source = Population.normalized({"a": Fraction(1)})
    target = Population.normalized({"a": Fraction(1), "b": Fraction(1)})
    with pytest.raises(Refused, match="POSITIVITY_VIOLATION"):
        support_overlap(source, target)
