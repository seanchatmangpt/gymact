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

AUTHORITY = "urn:authority:prod"
CAPABILITY = "urn:gymact:memory:capability:set"


def capsule() -> CapsuleIdentity:
    return CapsuleIdentity(
        source_digest="source",
        validator_digest="validator",
        toolchain_digest="toolchain",
        config_digest="config",
        environment_digest="environment",
    )


def test_execution_capsule_reuses_verifier_without_crowning_new_subject() -> None:
    identity = capsule()
    verifier = VerifierCapsuleReceipt(
        capsule=identity,
        validation=ValidationPack(
            command="pytest",
            exit_code=0,
            evidence_refs=("receipt:validator",),
            standing=Standing.ALIVE,
        ),
        receipt_ref="receipt:validator",
    )
    verifier_only = evaluate_capsule_reuse(
        verifier,
        identity,
        subject_digest="new-subject",
    )
    assert verifier_only.verifier_reusable
    assert not verifier_only.subject_reusable
    assert verifier_only.standing is Standing.STRUCTURAL

    subject = SubjectCapsuleReceipt(
        capsule=identity,
        subject_digest="subject-1",
        executed=True,
        verified=True,
        standing=Standing.ALIVE,
        receipt_ref="receipt:subject",
    )
    exact = evaluate_capsule_reuse(
        verifier,
        identity,
        cached_subject=subject,
        subject_digest="subject-1",
    )
    assert exact.subject_reusable
    assert exact.standing is Standing.ALIVE
    drift = evaluate_capsule_reuse(
        verifier,
        identity.model_copy(update={"config_digest": "changed"}),
    )
    assert drift.standing is Standing.STALE


def test_compile_out_recipe_is_hot_only_under_exact_policy_and_verifier_identity() -> None:
    identity = RecipeIdentity(
        problem_identity="problem",
        environment_identity="environment",
        authority_class="deploy",
        policy_revision="policy-1",
        verifier_ref="verifier-1",
        action_ref="action-1",
        input_contract_digest="schema-1",
    )
    recipe = compile_recipe(
        identity,
        candidate_ref="candidate-1",
        source_receipt_refs=("receipt-1", "receipt-2"),
    )
    hot = admit_compiled_recipe(recipe, identity)
    assert hot.admitted
    assert hot.model_required is False
    assert hot.standing is Standing.CANDIDATE
    stale = admit_compiled_recipe(
        recipe,
        identity.model_copy(update={"policy_revision": "policy-2"}),
    )
    assert not stale.admitted
    assert stale.model_required
    assert stale.standing is Standing.STALE


def test_decision_cache_reuses_candidates_and_positive_refusals_without_authority() -> None:
    key = DecisionKey(
        problem_identity="problem",
        environment_identity="environment",
        authority_class="deploy",
        policy_revision="policy-1",
        subject_revision="rev-1",
    )
    cache = DecisionCache()
    cache.put_candidate(
        CandidateDecision(
            key=key,
            candidate_refs=("candidate-1",),
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


def test_errc_ledger_is_complete_and_covers_all_four_moves() -> None:
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
