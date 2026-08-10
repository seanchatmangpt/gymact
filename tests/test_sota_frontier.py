from __future__ import annotations

import pytest

from gymact.sota import FrontierResult, SotaAdmissionError, StandingEvidence, dominates, pareto_frontier, sota_claim


def evidence(*, replay: bool = True) -> StandingEvidence:
    return StandingEvidence("subject:abc", "experiment:def", "receipt:123", "verifier:456", replay)


def result(result_id: str, quality: float, efficiency: float) -> FrontierResult:
    return FrontierResult(result_id, evidence(), {"quality": quality, "efficiency": efficiency})


def test_unreplayed_result_is_refused_before_comparison() -> None:
    candidate = FrontierResult("candidate", evidence(replay=False), {"quality": 1.0})
    with pytest.raises(SotaAdmissionError, match="SOTA_REPLAY_NOT_VERIFIED"):
        sota_claim(candidate, ())


def test_missing_receipt_binding_is_refused() -> None:
    candidate = FrontierResult(
        "candidate",
        StandingEvidence("subject", "experiment", "", "verifier", True),
        {"quality": 1.0},
    )
    with pytest.raises(SotaAdmissionError, match="SOTA_MISSING_BINDING:receipt"):
        candidate.admit()


def test_pareto_frontier_preserves_non_dominated_tradeoffs() -> None:
    balanced = result("balanced", 0.95, 0.95)
    quality_only = result("quality-only", 0.99, 0.50)
    dominated = result("dominated", 0.90, 0.90)
    assert dominates(balanced, dominated)
    assert not dominates(quality_only, balanced)
    assert {item.result_id for item in pareto_frontier((balanced, quality_only, dominated))} == {"balanced", "quality-only"}


def test_metric_space_mismatch_is_refused_not_silently_projected() -> None:
    left = result("left", 1.0, 1.0)
    right = FrontierResult("right", evidence(), {"quality": 1.0})
    with pytest.raises(SotaAdmissionError, match="SOTA_METRIC_SPACE_MISMATCH"):
        dominates(left, right)


def test_sota_claim_is_bounded_to_declared_comparison_set() -> None:
    candidate = result("candidate", 0.99, 0.99)
    weaker = result("weaker", 0.90, 0.95)
    stronger = result("stronger", 1.00, 1.00)
    assert sota_claim(candidate, (weaker,)) is True
    assert sota_claim(candidate, (weaker, stronger)) is False
