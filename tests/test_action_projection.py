from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from gymact.action_contract import (
    ActionDefinition,
    ExpectedEffect,
    IdempotencyClass,
    ObservationConfidence,
    ReversalClass,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
)
from gymact.action_projection import (
    CanonicalActionContract,
    project_capability,
    project_manufacture,
    project_move,
    project_possibility_graph,
)
from gymact.models import Consequence


def _action() -> ActionDefinition:
    return ActionDefinition(
        semantic_id="urn:test:action:set",
        provider_ref="urn:test:provider",
        capability_ref="urn:test:capability:set",
        subject_type="urn:test:subject-type",
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        },
        output_schema={"type": "object"},
        preconditions=("urn:test:precondition:ready",),
        expected_effects=(
            ExpectedEffect(predicate="urn:test:predicate:value", parameters={"value": 1}),
        ),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:test:observer",
            expected={"value": 1},
            minimum_confidence=ObservationConfidence.INDEPENDENT_CHANNEL,
        ),
        idempotency=IdempotencyClass.IDEMPOTENT,
        reversal=ReversalClass.REVERSIBLE,
    )


def test_action_definition_is_single_digest_bound_projection_source() -> None:
    action = _action()
    first = CanonicalActionContract.from_action(action)
    second = CanonicalActionContract.from_action(action)

    assert first == second
    assert first.contract_digest == second.contract_digest
    assert first.do_authority is False

    changed = action.model_copy(
        update={
            "verification": action.verification.model_copy(
                update={"expected": {"value": 2}}
            )
        }
    )
    assert CanonicalActionContract.from_action(changed).contract_digest != first.contract_digest


def test_forged_contract_digest_is_refused() -> None:
    with pytest.raises(ValidationError, match="ACTION_CONTRACT_DIGEST_MISMATCH"):
        CanonicalActionContract(action=_action(), contract_digest="0" * 64)


def test_all_runtime_and_manufacture_views_bind_same_action() -> None:
    contract = CanonicalActionContract.from_action(_action())
    subject = SubjectRef(
        semantic_id="urn:test:subject:1",
        provider_ref=contract.action.provider_ref,
        revision="rev-1",
    )

    capability = project_capability(contract)
    move = project_move(contract, subject_ref=subject.semantic_id)
    graph = project_possibility_graph(contract, subject=subject)
    manufacture = project_manufacture(contract)

    assert capability.iri == contract.action.capability_ref
    assert capability.consequence is Consequence.DO
    assert move.capability_ref == contract.action.capability_ref
    assert move.input_schema == contract.action.input_schema
    assert manufacture.source_contract_digest == contract.contract_digest
    assert manufacture.action_ref == contract.action.semantic_id
    assert manufacture.capability_ref == contract.action.capability_ref

    semantic_refs = {item.semantic_ref for item in graph.objects}
    assert contract.action.semantic_id in semantic_refs
    assert contract.action.capability_ref in semantic_refs
    assert contract.action.verification.observer_ref in semantic_refs


def test_manufacture_projection_cannot_smuggle_execution_authority() -> None:
    projection = project_manufacture(CanonicalActionContract.from_action(_action()))
    encoded = json.dumps(projection.model_dump(mode="json"), sort_keys=True).lower()

    assert projection.do_authority is False
    for forbidden in (
        "executiongrant",
        "execution_grant",
        '"nonce"',
        '"principal"',
        '"authority_ref"',
        '"permission"',
        '"token"',
    ):
        assert forbidden not in encoded
