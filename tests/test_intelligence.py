from __future__ import annotations

from gymact.intelligence import (
    CognitionEpisode,
    CompileOutObservation,
    IntelligenceRegime,
    detect_compilation_candidate,
    route_intelligence,
)


def episode(receipt: str, *, tokens: int = 100) -> CognitionEpisode:
    return CognitionEpisode(
        problem_identity="problem-1",
        environment_identity="environment-1",
        authority_class="read-write:bounded",
        model_tokens=tokens,
        monetary_cost=1.0,
        wall_time_s=2.0,
        verified=True,
        receipt_ref=receipt,
    )


def test_hot_path_is_indexed_and_model_optional() -> None:
    decision = route_intelligence(
        known_identity=True,
        pareto_candidates=("provider-a",),
    )
    assert decision.regime is IntelligenceRegime.HOT
    assert decision.model_required is False


def test_warm_path_is_bounded_and_cold_path_preserves_novelty() -> None:
    warm = route_intelligence(
        known_identity=True,
        pareto_candidates=("a", "b", "c", "d"),
    )
    assert warm.regime is IntelligenceRegime.WARM
    assert warm.candidate_refs == ("a", "b", "c")
    assert warm.model_required is False

    cold = route_intelligence(
        known_identity=False,
        pareto_candidates=("candidate",),
    )
    assert cold.regime is IntelligenceRegime.COLD
    assert cold.model_required is True


def test_repeated_verified_cognition_becomes_compilation_candidate() -> None:
    candidate = detect_compilation_candidate(
        (episode("receipt-1"), episode("receipt-2"))
    )
    assert candidate.candidate is True
    assert candidate.repetitions == 2
    assert candidate.model_tokens == 200
    assert candidate.reason == "REPEATED_VERIFIED_COGNITION"


def test_compile_out_requires_zero_tokens_and_preserved_law() -> None:
    observed = CompileOutObservation(
        cold_model_tokens=1000,
        hot_model_tokens=0,
        cold_cost=5.0,
        hot_cost=0.1,
        cold_wall_time_s=10.0,
        hot_wall_time_s=0.5,
        authority_preserved=True,
        verification_preserved=True,
        cold_receipt_ref="cold-receipt",
        hot_receipt_ref="hot-receipt",
    )
    assert observed.compiled_out is True
    weakened = observed.model_copy(update={"verification_preserved": False})
    assert weakened.compiled_out is False
