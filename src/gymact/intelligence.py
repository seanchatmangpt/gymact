"""Three-speed intelligence and cognition compile-out primitives.

This module chooses only *candidate* capability paths. It has no execution authority.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from gymact.models import FrozenModel


class IntelligenceRegime(StrEnum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class SelectionDecision(FrozenModel):
    regime: IntelligenceRegime
    candidate_refs: tuple[str, ...]
    model_required: bool
    reason: str


def route_intelligence(
    *,
    known_identity: bool,
    pareto_candidates: tuple[str, ...],
    warm_width: int = 3,
) -> SelectionDecision:
    """Route known identity to indexed HOT/WARM paths; novelty remains COLD."""
    if warm_width < 1:
        raise ValueError("WARM_WIDTH_MUST_BE_POSITIVE")
    if not known_identity or not pareto_candidates:
        return SelectionDecision(
            regime=IntelligenceRegime.COLD,
            candidate_refs=pareto_candidates[:warm_width],
            model_required=True,
            reason="NOVEL_OR_UNINDEXED_SUBJECT",
        )
    if len(pareto_candidates) == 1:
        return SelectionDecision(
            regime=IntelligenceRegime.HOT,
            candidate_refs=pareto_candidates,
            model_required=False,
            reason="INDEXED_SINGLE_CANDIDATE",
        )
    return SelectionDecision(
        regime=IntelligenceRegime.WARM,
        candidate_refs=pareto_candidates[:warm_width],
        model_required=False,
        reason="INDEXED_BOUNDED_RACE",
    )


class CognitionEpisode(FrozenModel):
    problem_identity: str = Field(min_length=1)
    environment_identity: str = Field(min_length=1)
    authority_class: str = Field(min_length=1)
    model_tokens: int = Field(ge=0)
    monetary_cost: float = Field(ge=0.0)
    wall_time_s: float = Field(ge=0.0)
    verified: bool
    receipt_ref: str = Field(min_length=1)


class CompilationCandidate(FrozenModel):
    candidate: bool
    equivalence_key: tuple[str, str, str]
    repetitions: int
    model_tokens: int
    receipt_refs: tuple[str, ...]
    reason: str


def detect_compilation_candidate(
    episodes: tuple[CognitionEpisode, ...],
    *,
    minimum_repetitions: int = 2,
) -> CompilationCandidate:
    """Repeated verified cognition over one admitted equivalence class is debt."""
    if minimum_repetitions < 2:
        raise ValueError("MINIMUM_REPETITIONS_MUST_BE_AT_LEAST_TWO")
    if not episodes:
        raise ValueError("COGNITION_EPISODES_REQUIRED")
    first = episodes[0]
    key = (
        first.problem_identity,
        first.environment_identity,
        first.authority_class,
    )
    equivalent = tuple(
        episode
        for episode in episodes
        if (
            episode.problem_identity,
            episode.environment_identity,
            episode.authority_class,
        )
        == key
        and episode.verified
    )
    tokens = sum(episode.model_tokens for episode in equivalent)
    candidate = len(equivalent) >= minimum_repetitions and tokens > 0
    return CompilationCandidate(
        candidate=candidate,
        equivalence_key=key,
        repetitions=len(equivalent),
        model_tokens=tokens,
        receipt_refs=tuple(episode.receipt_ref for episode in equivalent),
        reason=(
            "REPEATED_VERIFIED_COGNITION"
            if candidate
            else "INSUFFICIENT_EQUIVALENT_VERIFIED_COGNITION"
        ),
    )


class CompileOutObservation(FrozenModel):
    cold_model_tokens: int = Field(gt=0)
    hot_model_tokens: int = Field(ge=0)
    cold_cost: float = Field(gt=0.0)
    hot_cost: float = Field(ge=0.0)
    cold_wall_time_s: float = Field(gt=0.0)
    hot_wall_time_s: float = Field(ge=0.0)
    authority_preserved: bool
    verification_preserved: bool
    cold_receipt_ref: str = Field(min_length=1)
    hot_receipt_ref: str = Field(min_length=1)

    @property
    def compiled_out(self) -> bool:
        return (
            self.hot_model_tokens == 0
            and self.hot_cost < self.cold_cost
            and self.hot_wall_time_s <= self.cold_wall_time_s
            and self.authority_preserved
            and self.verification_preserved
        )
