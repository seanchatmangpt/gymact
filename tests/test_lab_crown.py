from __future__ import annotations

import pytest
from pydantic import ValidationError

from gymact.action_contract import (
    ActionDefinition,
    ExpectedEffect,
    ObservationConfidence,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
)
from gymact.lab import (
    CapabilityCacheEntry,
    CostPoint,
    EmpiricalProviderIndex,
    ProblemSignature,
    ProjectionKind,
    ProviderBenchmarkRecord,
    ProviderFamily,
    SelfPlayKind,
    TransitionMetrics,
    VCTObservation,
    differential_verdict,
    find_crossover,
    manufacture_self_play,
    pareto_frontier,
    project_action,
)
from gymact.models import Standing


def action() -> ActionDefinition:
    return ActionDefinition(
        semantic_id="urn:gymact:test:set",
        provider_ref="urn:gymact:test:provider",
        capability_ref="urn:gymact:test:cap:set",
        subject_type="schema:Thing",
        input_schema={"type": "object", "properties": {"value": {"type": "integer"}}},
        preconditions=("subject-exists",),
        expected_effects=(ExpectedEffect(predicate="value-set"),),
        verification=VerificationStrategy(
            kind=VerificationKind.PREDICATE,
            observer_ref="urn:gymact:test:observer",
        ),
    )


def signature() -> ProblemSignature:
    return ProblemSignature(
        deterministic=True,
        fully_observable=True,
        discrete=True,
        finite_horizon=True,
    )


def record(
    provider: str,
    *,
    cost: float,
    time: float,
    quality: float = 1.0,
) -> ProviderBenchmarkRecord:
    return ProviderBenchmarkRecord(
        action_ref=action().semantic_id,
        provider_ref=provider,
        signature=signature(),
        environment="local",
        hardware="cloud-test",
        metrics=TransitionMetrics(
            wall_time_s=time,
            monetary_cost=cost,
            quality=quality,
            verification_confidence=ObservationConfidence.INDEPENDENT_CHANNEL,
        ),
        result=Standing.ALIVE,
        receipt_ref=f"urn:receipt:{provider}",
    )


def test_pareto_selection_removes_dominated_provider() -> None:
    fast = record("fast", cost=1.0, time=1.0)
    cheap = record("cheap", cost=0.5, time=2.0)
    dominated = record("dominated", cost=2.0, time=3.0)
    frontier = pareto_frontier((fast, cheap, dominated))
    assert {item.provider_ref for item in frontier} == {"fast", "cheap"}
    index = EmpiricalProviderIndex()
    for item in (fast, cheap, dominated):
        index.record(item)
    selected = index.query(action_ref=action().semantic_id, signature=signature())
    assert {item.provider_ref for item in selected} == {"fast", "cheap"}


def test_capability_cache_refuses_authority_material() -> None:
    with pytest.raises(ValidationError, match="CAPABILITY_CACHE_AUTHORITY_LEAK"):
        CapabilityCacheEntry(
            problem_identity="p",
            environment_identity="e",
            action_ref="a",
            provider_ref="provider",
            evidence_refs=("receipt",),
            metadata={"authority_ref": "must-not-cache"},
        )


def test_all_projections_preserve_identity_without_authority() -> None:
    value = action()
    projections = [project_action(value, kind) for kind in ProjectionKind]
    assert {item.kind for item in projections} == set(ProjectionKind)
    assert all(item.action_ref == value.semantic_id for item in projections)
    assert all(item.capability_ref == value.capability_ref for item in projections)
    assert all(item.authority_transferred is False for item in projections)
    a2a = next(item for item in projections if item.kind is ProjectionKind.A2A)
    assert a2a.payload["authorization"] is None


def test_self_play_manufactures_required_falsifiers() -> None:
    subject = SubjectRef(semantic_id="urn:subject:1", provider_ref="subject", revision="abc")
    scenarios = manufacture_self_play(action(), subject)
    kinds = {scenario.kind for scenario in scenarios}
    assert {
        SelfPlayKind.VALID,
        SelfPlayKind.STALE_REVISION,
        SelfPlayKind.MISSING_AUTHORITY,
        SelfPlayKind.LOST_ACK,
        SelfPlayKind.PARTIAL_EFFECT,
        SelfPlayKind.WRONG_EFFECT,
        SelfPlayKind.DUPLICATE_REQUEST,
        SelfPlayKind.REPLAY_MISMATCH,
    } <= kinds


def test_differential_verifier_preserves_uncertainty() -> None:
    assert differential_verdict("a", "a").standing is Standing.ALIVE
    disagreement = differential_verdict("a", "b")
    assert disagreement.agrees is False
    assert disagreement.standing is Standing.UNCERTAIN
    with pytest.raises(ValueError, match="MULTIPLE_ORACLES"):
        differential_verdict("only-one")


def test_vct_compile_out_metrics_and_crossover() -> None:
    observation = VCTObservation(
        verified_transitions=8,
        wall_time_s=2.0,
        monetary_cost=4.0,
        human_intervention_factor=1.0,
        hot_transitions=5,
        warm_transitions=2,
        total_transitions=10,
        frontier_model_tokens=400,
    )
    assert observation.vct == 1.0
    assert observation.rho == 0.7
    assert observation.kappa == 0.02
    crossover = find_crossover(
        (
            CostPoint(repetitions=1, frontier_agent_cost=1.0, gymact_cost=4.0),
            CostPoint(repetitions=10, frontier_agent_cost=8.0, gymact_cost=6.0),
            CostPoint(repetitions=100, frontier_agent_cost=70.0, gymact_cost=9.0),
        )
    )
    assert crossover.observed is True
    assert crossover.repetitions == 10


def test_provider_family_preserves_target_ecology() -> None:
    values = {item.value for item in ProviderFamily}
    assert {
        "browser",
        "kubernetes",
        "cloud",
        "infrastructure_as_code",
        "mcp",
        "a2a",
        "bpmn",
        "robotics",
        "industrial_ot",
        "enterprise_saas",
    } <= values
