from __future__ import annotations

import pytest
from pydantic import ValidationError

from gymact import dcm
from gymact.environment_evolution import (
    EnvironmentEvolutionCourt,
    EvolutionCandidate,
    EvolutionDecisionKind,
    EvolutionDecisionPoint,
    EvolutionEcosystemBinding,
    EvolutionEvent,
    EvolutionEventOperation,
    EvolutionSeed,
    EvolutionValidation,
    task_request_digest,
)
from gymact.models import Standing

A = "blake3:" + "a" * 64
B = "blake3:" + "b" * 64
C = "blake3:" + "c" * 64
D = "blake3:" + "d" * 64
E = "blake3:" + "e" * 64
F = "blake3:" + "f" * 64
G = "blake3:" + "0" * 64
H = "blake3:" + "9" * 64
MARKETPLACE_SHA = "22f83777d950d1022b5a028793b3e2aa477d2047"
SJIRA_BASE_SHA = "9085c45a3d28df48635656ad9e2aa76dcaac06d4"
TASK = "Reconcile the approved budget for the reporting date."


def seed(*, min_chain: int = 1) -> EvolutionSeed:
    return EvolutionSeed(
        seed_id="seed:budget:0",
        generation=0,
        environment_digest=A,
        task_request=TASK,
        task_request_digest=task_request_digest(TASK),
        reference_outcome_digest=B,
        evaluator_digest=C,
        history_digest=D,
        history_event_ids=(),
        last_event_sequence=-1,
        min_evidence_chain_length=min_chain,
    )


def ecosystem() -> EvolutionEcosystemBinding:
    return EvolutionEcosystemBinding(
        marketplace_commit_sha=MARKETPLACE_SHA,
        autofde_selection_digest=E,
        sjira_work_order_id="GYMACT-EVOLVE-26925-001",
        sjira_base_sha=SJIRA_BASE_SHA,
        sa2a_candidate_digest=F,
    )


def point(index: int, *, chain: int = 1) -> EvolutionDecisionPoint:
    kinds = (
        EvolutionDecisionKind.TEMPORAL,
        EvolutionDecisionKind.EXCLUSION,
        EvolutionDecisionKind.NUMERICAL,
    )
    return EvolutionDecisionPoint(
        decision_id=f"dp-{index}",
        kind=kinds[index],
        plausible_wrong_choice=f"plausible-wrong-{index}",
        resolving_evidence_refs=(f"urn:evidence:{index}",),
        rejecting_check_ref=f"urn:check:{index}",
        evidence_chain_length=chain,
    )


def candidate(
    *,
    task: str = TASK,
    points: tuple[EvolutionDecisionPoint, ...] | None = None,
    events: tuple[EvolutionEvent, ...] | None = None,
) -> EvolutionCandidate:
    actual_points = points if points is not None else tuple(point(i) for i in range(3))
    actual_events = events if events is not None else (
        EvolutionEvent(
            event_id="event-0",
            sequence=0,
            operation=EvolutionEventOperation.MODIFY,
            target_ref="budget/approval.json",
            consequence_digest=E,
        ),
        EvolutionEvent(
            event_id="event-1",
            sequence=1,
            operation=EvolutionEventOperation.CREATE,
            target_ref="budget/revision.json",
            consequence_digest=F,
            depends_on_event_ids=("event-0",),
        ),
    )
    return EvolutionCandidate(
        candidate_id="variant:budget:1",
        generation=1,
        parent_environment_digest=A,
        parent_history_digest=D,
        task_request=task,
        task_request_digest=task_request_digest(task),
        direction="increase temporal/version ambiguity while preserving resolvability",
        generator_ref="urn:autofde:planner:environment-evolution",
        generator_digest=A,
        parent_candidate_digest=None,
        parent_lineage_digest=None,
        mutation_operator_digest=C,
        mutation_seed=26925,
        ecosystem=ecosystem(),
        new_environment_digest=E,
        reference_outcome_digest=F,
        evaluator_digest=G,
        decision_points=actual_points,
        events=actual_events,
        failure_feedback_digests=(B,),
    )


def validation(**updates) -> EvolutionValidation:
    current = seed()
    proposal = candidate()
    values = {
        "observer_ref": "urn:gymact:verifier:evolution",
        "observer_producer_digest": H,
        "evidence_digest": G,
        "observed_seed_digest": current.seed_digest,
        "observed_candidate_digest": proposal.candidate_digest,
        "observed_parent_environment_digest": A,
        "observed_task_request_digest": task_request_digest(TASK),
        "observed_environment_digest": E,
        "observed_history_digest": proposal.event_history_digest,
        "evaluator_digest": proposal.evaluator_digest,
        "recurring_failure_digests": (),
        "structural_checks_passed": True,
        "history_checks_passed": True,
        "material_placement_checks_passed": True,
        "evaluation_asset_syntax_passed": True,
        "shortcut_audit_passed": True,
        "new_reference_passed": True,
        "previous_reference_failed": True,
        "decision_point_checks_passed": True,
    }
    values.update(updates)
    return EvolutionValidation(**values)


def test_admitted_variant_advances_seed_without_granting_do_authority() -> None:
    court = EnvironmentEvolutionCourt()
    current = seed()
    proposal = candidate()

    transition = court.advance(current, proposal, validation())

    assert transition.admission.admitted is True
    assert transition.admission.standing is Standing.STRUCTURAL
    assert transition.admission.authority == "none"
    assert transition.authority == "none"
    assert transition.next_seed.generation == 1
    assert transition.next_seed.task_request == current.task_request
    assert transition.next_seed.task_request_digest == current.task_request_digest
    assert transition.next_seed.environment_digest == proposal.new_environment_digest
    assert transition.next_seed.reference_outcome_digest == proposal.reference_outcome_digest
    assert transition.next_seed.evaluator_digest == proposal.evaluator_digest
    assert transition.next_seed.history_event_ids == ("event-0", "event-1")
    assert transition.next_seed.source_candidate_digest == proposal.candidate_digest
    assert transition.next_seed.lineage_digest == proposal.mutation_lineage_digest
    assert transition.replay_receipt.lineage_digest == proposal.mutation_lineage_digest
    assert transition.replay_receipt.next_seed_digest == transition.next_seed.seed_digest
    assert transition.replay_receipt.authority == "none"
    assert "EnvironmentEvolutionCourt" in dcm.__all__


def test_task_request_change_is_refused_even_when_candidate_is_self_consistent() -> None:
    changed = candidate(task=TASK + " changed")
    court = EnvironmentEvolutionCourt()

    admission = court.qualify(seed(), changed, validation())

    assert admission.admitted is False
    assert "TASK_REQUEST_CHANGED" in admission.reasons
    assert "TASK_REQUEST_DIGEST_CHANGED" in admission.reasons
    with pytest.raises(ValueError, match="ENVIRONMENT_EVOLUTION_REFUSED"):
        court.advance(seed(), changed, validation())


def test_fewer_than_three_counter_default_points_is_refused() -> None:
    proposal = candidate(points=(point(0), point(1)))
    admission = EnvironmentEvolutionCourt().qualify(seed(), proposal, validation())

    assert admission.admitted is False
    assert "INSUFFICIENT_DECISION_POINTS" in admission.reasons


def test_evidence_chain_may_not_regress_across_generations() -> None:
    current = seed(min_chain=2)
    proposal = candidate(points=tuple(point(i, chain=1) for i in range(3)))
    admission = EnvironmentEvolutionCourt().qualify(current, proposal, validation())

    assert admission.admitted is False
    assert {
        "EVIDENCE_CHAIN_REGRESSION:dp-0",
        "EVIDENCE_CHAIN_REGRESSION:dp-1",
        "EVIDENCE_CHAIN_REGRESSION:dp-2",
    }.issubset(set(admission.reasons))


def test_causal_history_requires_prior_or_parent_event() -> None:
    broken = (
        EvolutionEvent(
            event_id="event-0",
            sequence=0,
            operation=EvolutionEventOperation.MODIFY,
            target_ref="budget/approval.json",
            consequence_digest=E,
            depends_on_event_ids=("future-event",),
        ),
    )
    admission = EnvironmentEvolutionCourt().qualify(
        seed(),
        candidate(events=broken),
        validation(),
    )

    assert admission.admitted is False
    assert "CAUSAL_DEPENDENCY_MISSING:event-0" in admission.reasons


def test_reference_and_evaluator_validation_are_independent_admission_edges() -> None:
    admission = EnvironmentEvolutionCourt().qualify(
        seed(),
        candidate(),
        validation(new_reference_passed=False, previous_reference_failed=False),
    )

    assert admission.admitted is False
    assert "NEW_REFERENCE_FAILED" in admission.reasons
    assert "PREVIOUS_REFERENCE_SURVIVED" in admission.reasons


def test_candidate_cannot_claim_do_authority() -> None:
    kwargs = candidate().model_dump(mode="python")
    kwargs["grants_do_authority"] = True

    with pytest.raises(ValidationError):
        EvolutionCandidate(**kwargs)



def test_evolution_replay_receipt_is_deterministic() -> None:
    court = EnvironmentEvolutionCourt()
    current = seed()
    proposal = candidate()
    observed = validation()

    left = court.advance(current, proposal, observed)
    right = court.advance(current, proposal, observed)

    assert left.replay_receipt == right.replay_receipt
    assert left.next_seed.seed_digest == right.next_seed.seed_digest
    assert left.admission.admission_digest == right.admission.admission_digest


def test_validator_must_be_independent_from_generator() -> None:
    proposal = candidate()
    admission = EnvironmentEvolutionCourt().qualify(
        seed(),
        proposal,
        validation(observer_producer_digest=proposal.generator_digest),
    )
    assert not admission.admitted
    assert "VALIDATOR_NOT_INDEPENDENT_FROM_GENERATOR" in admission.reasons


def test_recurring_failure_is_a_typed_falsifier() -> None:
    admission = EnvironmentEvolutionCourt().qualify(
        seed(),
        candidate(),
        validation(recurring_failure_digests=(B,)),
    )
    assert not admission.admitted
    assert f"FAILURE_RECURRED:{B}" in admission.reasons


def test_parent_lineage_is_bound_to_seed() -> None:
    proposal = candidate()
    values = proposal.model_dump(mode="python")
    values["parent_lineage_digest"] = H
    drifted = EvolutionCandidate(**values)
    admission = EnvironmentEvolutionCourt().qualify(
        seed(),
        drifted,
        validation(),
    )
    assert not admission.admitted
    assert "PARENT_LINEAGE_MISMATCH" in admission.reasons
