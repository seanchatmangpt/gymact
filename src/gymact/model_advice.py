"""Authority-free model advice over GymAct's DCM possibility graph.

The model may be a GNN, ONNX artifact, sklearn estimator, Nx model, LLM,
rule engine, planner, or any other producer. Advice can only reorder the
formally admitted candidate set. It cannot enlarge applicability, prune
admitted siblings, carry authority, or cross BRCE.
"""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import Field, model_validator

from gymact.combinatorial import AdmissionContext, PossibilityGraph, evaluate_morphism
from gymact.evidence import digest
from gymact.models import FrozenModel, Standing


class AdviceKind(StrEnum):
    FRONTIER = "FRONTIER"
    STATE_HEURISTIC = "STATE_HEURISTIC"
    ACTION_ORDER = "ACTION_ORDER"
    METHOD_ORDER = "METHOD_ORDER"
    BINDING_ORDER = "BINDING_ORDER"
    OUTCOME = "OUTCOME"
    REPAIR = "REPAIR"
    CONSEQUENCE = "CONSEQUENCE"
    EXPERIENCE = "EXPERIENCE"


class ModelCandidate(FrozenModel):
    candidate_ref: str = Field(min_length=1)
    score: float

    @model_validator(mode="after")
    def finite_score(self):
        if not math.isfinite(float(self.score)):
            raise ValueError("MODEL_ADVICE_SCORE_MUST_BE_FINITE")
        return self


class ModelAdvice(FrozenModel):
    planning_subject_identity: str = Field(min_length=1)
    possibility_graph_digest: str = Field(min_length=1)
    formal_projection_identity: str = Field(min_length=1)
    artifact_identity: str = Field(min_length=1)
    capability_ref: str = Field(min_length=1)
    input_projection_identity: str = Field(min_length=1)
    kind: AdviceKind
    candidates: tuple[ModelCandidate, ...]
    standing: Standing = Standing.CANDIDATE
    authorizes_actuation: bool = False

    @model_validator(mode="after")
    def powerless_unique_candidates(self):
        refs = tuple(candidate.candidate_ref for candidate in self.candidates)
        if len(refs) != len(set(refs)):
            raise ValueError("MODEL_ADVICE_CANDIDATE_REFS_MUST_BE_UNIQUE")
        if self.standing is not Standing.CANDIDATE:
            raise ValueError("MODEL_ADVICE_MUST_REMAIN_CANDIDATE")
        if self.authorizes_actuation:
            raise ValueError("MODEL_ADVICE_CANNOT_AUTHORIZE_ACTUATION")
        return self

    @property
    def advice_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class AdviceApplication(FrozenModel):
    advice_digest: str
    possibility_graph_digest: str
    ranked_admitted_refs: tuple[str, ...]
    excluded_formal_refs: tuple[tuple[str, str], ...]
    ignored_advice_refs: tuple[str, ...]
    standing: Standing = Standing.CANDIDATE
    authorizes_actuation: bool = False


def apply_model_advice(
    *,
    graph: PossibilityGraph,
    context: AdmissionContext,
    advice: ModelAdvice,
    formal_candidate_refs: tuple[str, ...],
) -> AdviceApplication:
    """Reorder, but never redefine, the formal candidate set.

    The formal caller supplies candidate refs. GymAct independently evaluates each
    morphism under the current AdmissionContext. Learned advice is consulted only
    after those evaluations and therefore cannot make an inapplicable or
    unauthorized morphism applicable.
    """

    if advice.possibility_graph_digest != graph.graph_digest:
        raise ValueError("MODEL_ADVICE_GRAPH_IDENTITY_MISMATCH")
    if len(formal_candidate_refs) != len(set(formal_candidate_refs)):
        raise ValueError("FORMAL_CANDIDATE_REFS_MUST_BE_UNIQUE")

    formal_set = set(formal_candidate_refs)
    known_morphisms = {morphism.morphism_id for morphism in graph.morphisms}
    unknown_formal = tuple(ref for ref in formal_candidate_refs if ref not in known_morphisms)
    if unknown_formal:
        raise ValueError(f"FORMAL_CANDIDATE_NOT_IN_GRAPH:{unknown_formal[0]}")

    admitted: list[str] = []
    excluded: list[tuple[str, str]] = []
    for ref in formal_candidate_refs:
        evaluation = evaluate_morphism(graph.morphism(ref), context)
        if evaluation.admitted:
            admitted.append(ref)
        else:
            excluded.append((ref, evaluation.reason))

    admitted_set = set(admitted)
    ranked_from_advice = tuple(
        candidate.candidate_ref
        for candidate in sorted(
            advice.candidates,
            key=lambda candidate: (-float(candidate.score), candidate.candidate_ref),
        )
        if candidate.candidate_ref in admitted_set
    )
    ranked_set = set(ranked_from_advice)
    ranked = (*ranked_from_advice, *(ref for ref in admitted if ref not in ranked_set))

    ignored = tuple(
        candidate.candidate_ref
        for candidate in advice.candidates
        if candidate.candidate_ref not in formal_set
    )

    return AdviceApplication(
        advice_digest=advice.advice_digest,
        possibility_graph_digest=graph.graph_digest,
        ranked_admitted_refs=ranked,
        excluded_formal_refs=tuple(excluded),
        ignored_advice_refs=ignored,
    )


__all__ = [
    "AdviceApplication",
    "AdviceKind",
    "ModelAdvice",
    "ModelCandidate",
    "apply_model_advice",
]
