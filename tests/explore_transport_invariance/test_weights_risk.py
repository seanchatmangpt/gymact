from fractions import Fraction

from gymact.explore_transport_invariance import (
    Cell,
    horvitz_thompson,
    importance_weights,
    self_normalized,
)


def test_weight_cap_changes_ess_and_estimators_remain_distinct() -> None:
    cells = (Cell("a", Fraction(3, 4), Fraction(1, 4)), Cell("b", Fraction(1, 4), Fraction(3, 4)))
    uncapped = importance_weights(cells)
    capped = importance_weights(cells, Fraction(2))
    assert capped.max_weight < uncapped.max_weight
    assert capped.ess > 0
    losses = (Fraction(0), Fraction(1))
    assert horvitz_thompson(losses, uncapped.weights) != self_normalized(losses, uncapped.weights)
