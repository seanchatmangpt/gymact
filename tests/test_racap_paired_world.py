import pytest
from pydantic import ValidationError

from gymact.racap_paired_world import (
    CapabilityObservation,
    PairedWorldCourt,
    PairedWorldIdentity,
    PairedWorldRun,
)


def _d(char: str) -> str:
    return "blake3:" + char * 64


def _identity(task: str = "b") -> PairedWorldIdentity:
    return PairedWorldIdentity(
        world_digest=_d("a"),
        task_digest=_d(task),
        seed=17,
        budget_digest=_d("c"),
        evaluator_digest=_d("d"),
    )


def _observation(capability: str, *, score: float, success: bool = True):
    return CapabilityObservation(
        capability_digest=_d(capability),
        outcome_digest=_d("e"),
        consequence_digest=_d("f"),
        receipt_digest=_d("1"),
        score=score,
        success=success,
        steps=11,
    )


def _run(task: str = "b", candidate: str = "3") -> PairedWorldRun:
    return PairedWorldRun(
        identity=_identity(task),
        champion=_observation("2", score=0.60),
        candidate=_observation(candidate, score=0.75),
    )


def test_paired_world_manufactures_evidence_but_no_promotion_authority() -> None:
    evidence = PairedWorldCourt().observe(_run())

    assert evidence.delta == pytest.approx(0.15)
    assert evidence.authority == "none"
    assert evidence.champion_receipt_digest == _d("1")
    assert evidence.candidate_receipt_digest == _d("1")
    assert evidence.evidence_digest.startswith("blake3:")


def test_cohort_refuses_duplicate_exact_world_identity() -> None:
    run = _run()

    with pytest.raises(ValueError, match="PAIRED_WORLD_DUPLICATE_IDENTITY"):
        PairedWorldCourt().observe_cohort((run, run))


def test_cohort_refuses_mixed_candidate_pair() -> None:
    with pytest.raises(ValueError, match="PAIRED_WORLD_MIXED_CAPABILITY_PAIR"):
        PairedWorldCourt().observe_cohort((_run("b", "3"), _run("4", "4")))


def test_non_finite_score_is_refused() -> None:
    with pytest.raises(ValidationError, match="PAIRED_WORLD_NON_FINITE_SCORE"):
        _observation("2", score=float("nan"))
