from __future__ import annotations

import pytest
from pydantic import ValidationError

from gymact.action_contract import (
    ActionDefinition,
    AuthorityRequirement,
    ExecutionGrant,
    ExpectedEffect,
    IdempotencyClass,
    ObservationConfidence,
    ReconciliationDisposition,
    ReconciliationResult,
    ReversalClass,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
    admit_execution,
    construct_prepared_action,
)
from gymact.models import Standing


def base_action(**updates: object) -> ActionDefinition:
    data: dict[str, object] = {
        "semantic_id": "urn:test:action:set",
        "provider_ref": "urn:test:provider",
        "capability_ref": "urn:test:cap:set",
        "subject_type": "schema:Thing",
        "input_schema": {"type": "object"},
        "expected_effects": (
            ExpectedEffect(predicate="state_equals", parameters={"x": 1}),
        ),
        "verification": VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:test:observer",
            expected={"x": 1},
            minimum_confidence=ObservationConfidence.INDEPENDENT_CHANNEL,
        ),
        "authority": AuthorityRequirement(
            capability_refs=("urn:test:authority:set",),
        ),
    }
    data.update(updates)
    return ActionDefinition.model_validate(data)


def test_unknown_action_is_structurally_valid() -> None:
    assert base_action().standing is Standing.UNKNOWN


def test_conditional_idempotency_requires_fields() -> None:
    with pytest.raises(
        ValidationError,
        match="CONDITIONAL_IDEMPOTENCY_REQUIRES_KEY_FIELDS",
    ):
        base_action(idempotency=IdempotencyClass.CONDITIONALLY_IDEMPOTENT)


def test_compensation_requires_reference() -> None:
    with pytest.raises(
        ValidationError,
        match="COMPENSATABLE_ACTION_REQUIRES_COMPENSATION_ACTION_REF",
    ):
        base_action(reversal=ReversalClass.COMPENSATABLE)


def test_alive_requires_execution_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match="ALIVE_ACTION_REQUIRES_EXECUTION_EVIDENCE",
    ):
        base_action(standing=Standing.ALIVE)
    action = base_action(standing=Standing.ALIVE, evidence_refs=("urn:receipt:1",))
    assert action.standing is Standing.ALIVE


def test_quorum_means_multiple_oracles() -> None:
    with pytest.raises(
        ValidationError,
        match="QUORUM_VERIFICATION_REQUIRES_AT_LEAST_TWO_ORACLES",
    ):
        VerificationStrategy(kind=VerificationKind.QUORUM, observer_ref="urn:o")


def test_uncertain_reconciliation_cannot_smuggle_retry() -> None:
    with pytest.raises(
        ValidationError,
        match="UNCERTAIN_OUTCOME_CANNOT_IMPLY_RETRY",
    ):
        ReconciliationResult(
            disposition=ReconciliationDisposition.STILL_UNCERTAIN,
            standing=Standing.UNCERTAIN,
            retry_admitted=True,
        )


def test_construct_and_admit_preserve_revision_identity() -> None:
    action = base_action(input_schema={"type": "object", "required": ["value"]})
    subject = SubjectRef(
        semantic_id="urn:subject:1",
        provider_ref="resource-1",
        revision="abc",
    )
    prepared = construct_prepared_action(
        action,
        episode_id="episode-1",
        subject=subject,
        payload={"value": 1},
        admission_digest="digest-1",
        idempotency_key="key-1",
    )
    grant = ExecutionGrant(
        principal="urn:principal:test",
        action_ref=action.semantic_id,
        subject=subject,
        capability_ref=action.capability_ref,
        authority_ref="urn:authority:test",
        policy_revision="policy-1",
        admitted_observation_ref="urn:observation:1",
        intended_effects=action.expected_effects,
        nonce="nonce-1",
    )
    assert admit_execution(action, prepared, grant, current_revision="abc").admitted is True
    stale = admit_execution(action, prepared, grant, current_revision="def")
    assert stale.admitted is False
    assert stale.reason == "REVISION_MISMATCH_REFUSED"


def test_construct_rejects_input_schema_mismatch() -> None:
    action = base_action(input_schema={"type": "object", "required": ["value"]})
    subject = SubjectRef(semantic_id="urn:subject:1", provider_ref="resource-1")
    with pytest.raises(ValueError, match="PRECONDITION_REFUSED:INPUT_SCHEMA"):
        construct_prepared_action(
            action,
            episode_id="episode-1",
            subject=subject,
            payload={},
            admission_digest="digest-1",
            idempotency_key="key-1",
        )
