"""Chicago-style value courts for model advice over the real DCM evaluator."""

from __future__ import annotations

import pytest

from gymact.action_contract import ReversalClass
from gymact.combinatorial import (
    AdmissionContext,
    DecisionPhase,
    MorphismKind,
    MorphismRequirements,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
)
from gymact.model_advice import AdviceKind, ModelAdvice, ModelCandidate, apply_model_advice
from gymact.models import Standing


def _graph() -> PossibilityGraph:
    objects = tuple(
        PossibilityObject(
            object_id=object_id,
            kind=PossibilityObjectKind.ACTION,
            semantic_ref=f"urn:test:{object_id}",
        )
        for object_id in ("start", "rollback", "failover", "do")
    )
    morphisms = (
        PossibilityMorphism(
            morphism_id="m-rollback",
            source_id="start",
            target_id="rollback",
            kind=MorphismKind.PLAN,
            phase=DecisionPhase.SELECT,
            reversal=ReversalClass.REVERSIBLE,
        ),
        PossibilityMorphism(
            morphism_id="m-failover",
            source_id="start",
            target_id="failover",
            kind=MorphismKind.PLAN,
            phase=DecisionPhase.SELECT,
            reversal=ReversalClass.REVERSIBLE,
        ),
        PossibilityMorphism(
            morphism_id="m-do",
            source_id="start",
            target_id="do",
            kind=MorphismKind.ACTUATE,
            phase=DecisionPhase.DO,
            reversal=ReversalClass.IRREVERSIBLE,
            requirements=MorphismRequirements(execution_grant_required=True),
        ),
    )
    return PossibilityGraph(objects=objects, morphisms=morphisms)


def _advice(graph: PossibilityGraph) -> ModelAdvice:
    return ModelAdvice(
        planning_subject_identity="sha256:subject",
        possibility_graph_digest=graph.graph_digest,
        formal_projection_identity="sha256:fond-hddl",
        artifact_identity="sha256:onnx-model",
        capability_ref="https://schema.org/Action",
        input_projection_identity="sha256:rdf-features",
        kind=AdviceKind.ACTION_ORDER,
        candidates=(
            ModelCandidate(candidate_ref="not-formal", score=1.0),
            ModelCandidate(candidate_ref="m-do", score=0.99),
            ModelCandidate(candidate_ref="m-failover", score=0.91),
            ModelCandidate(candidate_ref="m-rollback", score=0.42),
        ),
    )


def test_model_can_reorder_only_independently_admitted_dcm_edges() -> None:
    graph = _graph()
    result = apply_model_advice(
        graph=graph,
        context=AdmissionContext(),
        advice=_advice(graph),
        formal_candidate_refs=("m-rollback", "m-failover", "m-do"),
    )

    assert result.ranked_admitted_refs == ("m-failover", "m-rollback")
    assert set(result.ranked_admitted_refs) == {"m-rollback", "m-failover"}
    assert result.excluded_formal_refs == (("m-do", "EXECUTION_GRANT_REQUIRED"),)
    assert result.ignored_advice_refs == ("not-formal",)
    assert result.standing is Standing.CANDIDATE
    assert not result.authorizes_actuation


def test_model_advice_is_bound_to_exact_possibility_graph_identity() -> None:
    graph = _graph()
    stale = _advice(graph).model_copy(
        update={"possibility_graph_digest": "sha256:stale"}
    )

    with pytest.raises(ValueError, match="MODEL_ADVICE_GRAPH_IDENTITY_MISMATCH"):
        apply_model_advice(
            graph=graph,
            context=AdmissionContext(),
            advice=stale,
            formal_candidate_refs=("m-rollback",),
        )


def test_model_advice_cannot_self_promote_or_authorize() -> None:
    graph = _graph()

    promoted = _advice(graph).model_dump(mode="python")
    promoted["standing"] = Standing.ALIVE
    with pytest.raises(ValueError, match="MODEL_ADVICE_MUST_REMAIN_CANDIDATE"):
        ModelAdvice.model_validate(promoted)

    authorized = _advice(graph).model_dump(mode="python")
    authorized["authorizes_actuation"] = True
    with pytest.raises(ValueError, match="MODEL_ADVICE_CANNOT_AUTHORIZE_ACTUATION"):
        ModelAdvice.model_validate(authorized)
