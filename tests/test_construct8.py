from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from gymact.action_contract import (
    ActionDefinition,
    AuthorityRequirement,
    CostModel,
    ExpectedEffect,
    IdempotencyClass,
    ReversalClass,
    VerificationKind,
    VerificationStrategy,
)
from gymact.action_projection import CanonicalActionContract
from gymact.construct8 import Construct8Word, encode_construct8
from gymact.construct8_projection import project_construct8


def _action() -> ActionDefinition:
    return ActionDefinition(
        semantic_id="urn:test:action:construct8",
        provider_ref="urn:test:provider",
        capability_ref="urn:test:capability",
        subject_type="urn:test:subject",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        preconditions=("urn:test:ready",),
        authority=AuthorityRequirement(
            capability_refs=("urn:test:capability:extra",),
            policy_refs=("urn:test:policy",),
        ),
        expected_effects=(ExpectedEffect(predicate="urn:test:changed"),),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:test:observer",
        ),
        idempotency=IdempotencyClass.IDEMPOTENT,
        reversal=ReversalClass.REVERSIBLE,
        cost=CostModel(monetary=1.0),
    )


def test_construct8_projects_execution_law_to_one_digest_bound_byte() -> None:
    contract = CanonicalActionContract.from_action(_action())
    word = project_construct8(contract)

    # 01 idempotency | 01 reversal | precondition | authority | output | cost
    assert word.value == 0xF5
    assert word.hex == "f5"
    assert word.idempotency is IdempotencyClass.IDEMPOTENT
    assert word.reversal is ReversalClass.REVERSIBLE
    assert word.has_preconditions is True
    assert word.has_explicit_authority_requirements is True
    assert word.has_output_schema is True
    assert word.has_declared_cost_or_risk is True
    assert word.source_contract_digest == contract.contract_digest
    assert word.action_ref == contract.action.semantic_id
    assert word.do_authority is False


def test_unknown_execution_law_stays_unknown_instead_of_being_inferred() -> None:
    action = _action().model_copy(
        update={
            "output_schema": {},
            "preconditions": (),
            "authority": AuthorityRequirement(),
            "idempotency": IdempotencyClass.UNKNOWN,
            "reversal": ReversalClass.UNKNOWN,
            "cost": CostModel(),
        }
    )

    assert encode_construct8(action) == 0
    word = project_construct8(CanonicalActionContract.from_action(action))
    assert word.idempotency is IdempotencyClass.UNKNOWN
    assert word.reversal is ReversalClass.UNKNOWN


def test_same_byte_does_not_collapse_distinct_canonical_semantics() -> None:
    first = CanonicalActionContract.from_action(_action())
    changed_action = _action().model_copy(
        update={
            "semantic_id": "urn:test:action:construct8:other",
            "expected_effects": (ExpectedEffect(predicate="urn:test:other-effect"),),
        }
    )
    second = CanonicalActionContract.from_action(changed_action)

    first_word = project_construct8(first)
    second_word = project_construct8(second)

    assert first_word.value == second_word.value
    assert first_word.source_contract_digest != second_word.source_contract_digest
    assert first_word.action_ref != second_word.action_ref


def test_construct8_range_is_exactly_one_octet() -> None:
    common = {
        "source_contract_digest": "a" * 64,
        "action_ref": "urn:test:action",
    }
    assert Construct8Word(value=0, **common).hex == "00"
    assert Construct8Word(value=255, **common).hex == "ff"

    with pytest.raises(ValidationError):
        Construct8Word(value=-1, **common)
    with pytest.raises(ValidationError):
        Construct8Word(value=256, **common)


def test_construct8_projection_cannot_smuggle_do_authority() -> None:
    word = project_construct8(CanonicalActionContract.from_action(_action()))
    encoded = json.dumps(word.model_dump(mode="json"), sort_keys=True).lower()

    assert word.do_authority is False
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
