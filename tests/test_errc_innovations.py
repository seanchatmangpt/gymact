from __future__ import annotations

import pytest

from gymact.action_contract import (
    ActionDefinition,
    ExecutionGrant,
    ExpectedEffect,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
    construct_prepared_action,
)
from gymact.authority import AllowListAuthorityResolver
from gymact.brce import BRCEBroker, BrokerRequest
from gymact.capsule import (
    CapsuleIdentity,
    SubjectCapsuleReceipt,
    ValidationPack,
    VerifierCapsuleReceipt,
    evaluate_capsule_reuse,
)
from gymact.compileout import RecipeIdentity, admit_compiled_recipe, compile_recipe
from gymact.decision_cache import CandidateDecision, DecisionCache, DecisionKey, RefusalDecision
from gymact.errc import ERRCMove, errc_summary, load_errc
from gymact.models import ActuationIntent, MaterializationIntent, Standing
from gymact.oracle import differential_verify, observe_oracle
from gymact.providers import MemoryProvider
from gymact.runtime import ProductionGymAct

AUTHORITY = "urn:test:authority"
CAPABILITY = "urn:gymact:memory:capability:set"


def test_capsule_reuses_validator_but_never_subject_alive() -> None:
    identity = CapsuleIdentity(
        source_digest="source",
        validator_digest="validator",
        toolchain_digest="toolchain",
        config_digest="config",
        environment_digest="environment",
    )
    pack = ValidationPack(identity=identity, verifier_ref="urn:verifier:1")
    verifier = VerifierCapsuleReceipt(
        identity=identity,
        validation_pack_digest=pack.pack_digest,
        receipt_refs=("urn:receipt:validator",),
        standing=Standing.ALIVE,
    )
    reuse = evaluate_capsule_reuse(identity, pack, verifier)
    assert reuse.validator_reusable
    assert reuse.verifier_standing is Standing.ALIVE
    assert reuse.subject_standing is Standing.UNKNOWN

    subject = SubjectCapsuleReceipt(
        identity=identity,
        subject_ref="urn:subject:1",
        execution_receipt_ref="urn:receipt:subject",
        verifier_receipt_ref="urn:receipt:validator",
        standing=Standing.ALIVE,
    )
    alive = evaluate_capsule_reuse(identity, pack, verifier, subject)
    assert alive.subject_standing is Standing.ALIVE


def test_compiled_recipe_is_candidate_and_never_caches_authority() -> None:
    identity = RecipeIdentity(
        problem_identity="problem",
        environment_identity="environment",
        authority_class="operator",
        policy_revision="policy-1",
        verifier_ref="urn:verifier:1",
        action_ref="urn:action:1",
        input_contract_digest="contract",
    )
    recipe = compile_recipe(
        identity,
        candidate_ref="urn:candidate:1",
        source_receipt_refs=("urn:receipt:1",),
    )
    assert not hasattr(recipe, "execution_grant")
    admitted = admit_compiled_recipe(recipe, identity)
    assert admitted.admitted
    assert admitted.standing is Standing.CANDIDATE
    assert admitted.model_required is False
    stale = admit_compiled_recipe(
        recipe,
        identity.model_copy(update={"policy_revision": "policy-2"}),
    )
    assert stale.standing is Standing.STALE
    assert stale.model_required


def test_decision_cache_keys_refusal_by_exact_revision_policy_and_verifier() -> None:
    key = DecisionKey(
        problem_identity="problem",
        environment_identity="env",
        subject_identity="subject",
        subject_revision="rev-1",
        authority_class="operator",
        policy_revision="policy-1",
        verifier_ref="verifier",
        capability_ref="capability",
    )
    cache = DecisionCache()
    cache.put_candidate(
        CandidateDecision(
            key=key,
            candidate_ref="candidate",
            evidence_refs=("receipt-1",),
        )
    )
    candidate = cache.resolve(key)
    assert candidate.cache_hit
    assert candidate.standing is Standing.CANDIDATE
    cache.put_refusal(
        RefusalDecision(
            key=key,
            reason="CAPABILITY_REFUSED",
            evidence_refs=("receipt-2",),
        )
    )
    refused = cache.resolve(key)
    assert refused.cache_hit
    assert refused.standing is Standing.REFUSED
    assert cache.resolve(key.model_copy(update={"subject_revision": "rev-2"})).cache_hit is False


def test_differential_oracle_requires_distinct_channels_and_quorum() -> None:
    first = observe_oracle(
        oracle_ref="provider-observer",
        channel_ref="provider-api",
        state={"x": 2},
    )
    second = observe_oracle(
        oracle_ref="raw-observer",
        channel_ref="raw-http",
        state={"x": 2},
    )
    verdict = differential_verify((first, second), expected={"x": 2})
    assert verdict.passed
    assert verdict.standing is Standing.ALIVE
    with pytest.raises(ValueError, match="CHANNELS_MUST_BE_DISTINCT"):
        differential_verify(
            (first, second.model_copy(update={"channel_ref": "provider-api"})),
            expected={"x": 2},
        )


def test_errc_ledger_is_complete_and_declares_dcm_as_canonical_authority() -> None:
    items = load_errc()
    summary = errc_summary(items)
    assert summary.complete
    assert set(summary.moves) == {move.value for move in ERRCMove}
    assert summary.statuses == {"SATISFIED": len(items)}
    assert summary.high_leverage


@pytest.mark.asyncio
async def test_production_runtime_refuses_raw_do_then_brce_executes_verified() -> None:
    runtime = ProductionGymAct(
        authority_resolver=AllowListAuthorityResolver({AUTHORITY})
    )
    runtime.register_provider(MemoryProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"x": 1}, "requires_authority": True},
            idempotency_key="prod-materialize",
        )
    )
    assert materialized.episode is not None
    episode = materialized.episode

    raw = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=CAPABILITY,
            payload={"key": "x", "value": 2},
            authority_ref=AUTHORITY,
            idempotency_key="raw-refused",
        )
    )
    assert raw.standing is Standing.REFUSED
    assert raw.receipt.reason == "BRCE_EXECUTION_GRANT_REQUIRED"
    assert (await runtime.observe(episode.episode_id)).state == {"x": 1}

    effect = ExpectedEffect(predicate="state", parameters={"x": 2})
    action = ActionDefinition(
        semantic_id="urn:action:set-x",
        provider_ref="urn:provider:memory",
        capability_ref=CAPABILITY,
        subject_type="schema:Thing",
        input_schema={
            "type": "object",
            "required": ["key", "value"],
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "integer"},
            },
        },
        expected_effects=(effect,),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:observer:memory",
            expected={"x": 2},
        ),
    )
    subject = SubjectRef(
        semantic_id="urn:subject:memory",
        provider_ref=episode.environment_id,
    )
    prepared = construct_prepared_action(
        action,
        episode_id=episode.episode_id,
        subject=subject,
        payload={"key": "x", "value": 2},
        admission_digest="observation-1",
        idempotency_key="brce-set",
    )
    grant = ExecutionGrant(
        principal="urn:principal:test",
        action_ref=action.semantic_id,
        subject=subject,
        capability_ref=CAPABILITY,
        authority_ref=AUTHORITY,
        policy_revision="policy-1",
        admitted_observation_ref="observation-1",
        intended_effects=(effect,),
        nonce="nonce-1",
    )
    verified = await BRCEBroker(runtime).execute(
        BrokerRequest(
            action=action,
            prepared=prepared,
            grant=grant,
            expected={"x": 2},
        )
    )
    assert verified.standing is Standing.ALIVE
    assert verified.receipt.verified is True
    assert (await runtime.observe(episode.episode_id)).state == {"x": 2}
