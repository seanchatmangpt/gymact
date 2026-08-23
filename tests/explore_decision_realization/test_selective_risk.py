import pytest

from gymact.explore_decision_realization import (
    ObservationPropensity,
    Refused,
    SelectiveLoss,
    brier_score,
    horvitz_thompson_risk,
    self_normalized_risk,
)


def test_selective_observation_correction_and_proper_score() -> None:
    propensity = ObservationPropensity("d-1", 0.5, "a" * 64)
    assert propensity.weight == 2.0
    rows = (SelectiveLoss(0.5, 0.5), SelectiveLoss(0.0, 1.0))
    assert horvitz_thompson_risk(rows, 4) == pytest.approx(0.25)
    assert self_normalized_risk(rows) == pytest.approx(1 / 3)
    assert brier_score(((0.9, True), (0.2, False))) == pytest.approx(0.025)
    with pytest.raises(Refused, match="POSITIVITY_VIOLATION"):
        ObservationPropensity("d-2", 0.0, "b" * 64)
