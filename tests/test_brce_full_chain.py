"""One chain, real objects, all six BRCE sub-requirements.

Chicago-style (real collaborators, state-based assertions; no unittest.mock,
Mock, patch, or monkeypatch anywhere in this file):

1. authority-refusal   -- raw ``act`` on ProductionGymAct is REFUSED without BRCE
2. brce-do              -- BRCEBroker.execute performs the real DO after an
                           admitted ExecutionGrant
3. independent-observation -- the post-state is observed back from the real
                           MemoryProvider, not read off the receipt
4. receipt              -- a real Receipt is appended to the runtime's real
                           MemoryReceiptLedger (``runtime.ledger``), not a stub
5. tamper-refusal       -- mutating a stored record's digest makes
                           ``runtime.ledger.verify()`` false and
                           ``replay_ledger`` refuse with EVIDENCE_CHAIN_INVALID
6. replay               -- ``replay_ledger`` over the untampered real ledger
                           validates the full evidence chain and identity

All six run against the same ``ProductionGymAct`` instance, the same
``BRCEBroker``, and the same ``runtime.ledger`` (a real
``gymact.evidence.MemoryReceiptLedger``) -- no fake Ledger/Receipt stand-ins.
"""
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
from gymact.evidence import MemoryReceiptLedger
from gymact.models import ActuationIntent, MaterializationIntent, Standing
from gymact.providers import MemoryProvider
from gymact.replay import ReplayExpectation, ReplayMode, replay_ledger
from gymact.runtime import ProductionGymAct

AUTHORITY = "urn:authority:prod"
CAPABILITY = "urn:gymact:memory:capability:set"


@pytest.mark.asyncio
async def test_brce_full_chain_all_six_subrequirements_real_runtime() -> None:
    runtime = ProductionGymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    runtime.register_provider(MemoryProvider())
    assert isinstance(runtime.ledger, MemoryReceiptLedger)

    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"x": 1}, "requires_authority": True},
            idempotency_key="full-chain-materialize",
        )
    )
    assert materialized.episode is not None
    episode = materialized.episode

    # --- 1. authority-refusal: raw act() is refused without a BRCE grant ---
    raw = await runtime.act(
        ActuationIntent(
            episode_id=episode.episode_id,
            capability=CAPABILITY,
            payload={"key": "x", "value": 2},
            authority_ref=AUTHORITY,
            idempotency_key="full-chain-raw-refused",
        )
    )
    assert raw.standing is Standing.REFUSED
    assert raw.receipt.reason == "BRCE_EXECUTION_GRANT_REQUIRED"
    assert (await runtime.observe(episode.episode_id)).state == {"x": 1}

    # --- 2. brce-do: BRCEBroker performs the real DO after an admitted grant ---
    effect = ExpectedEffect(predicate="state", parameters={"x": 2})
    action = ActionDefinition(
        semantic_id="urn:action:full-chain-set-x",
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
        idempotency_key="full-chain-brce-set",
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
        nonce="full-chain-nonce-1",
    )
    verified = await BRCEBroker(runtime).execute(
        BrokerRequest(action=action, prepared=prepared, grant=grant, expected={"x": 2})
    )
    assert verified.standing is Standing.ALIVE
    assert verified.receipt.verified is True

    # --- 3. independent-observation: state re-observed from the real provider ---
    post_observation = await runtime.observe(episode.episode_id)
    assert post_observation.state == {"x": 2}

    # --- 4. receipt: a real Receipt landed in the runtime's real ledger ---
    ledger = runtime.ledger
    records = ledger.records()
    assert any(r.receipt.receipt_id == verified.receipt.receipt_id for r in records)
    assert ledger.find(verified.receipt.receipt_id) is not None
    assert ledger.verify() is True

    # --- 6. replay: independent replay of the real, untampered ledger ---
    clean_report = replay_ledger(
        ledger,
        expected=ReplayExpectation(subject_ref=verified.receipt.subject_ref),
    )
    assert clean_report.valid is True
    assert clean_report.record_count == len(records)
    assert clean_report.mismatches == ()

    # --- 5. tamper-refusal: mutating a stored record is detected and refused ---
    original_record = ledger._records[0]
    ledger._records[0] = original_record.model_copy(update={"record_digest": "f" * 64})
    try:
        assert ledger.verify() is False
        tampered_report = replay_ledger(ledger)
        assert tampered_report.valid is False
        assert tampered_report.mismatches == ("EVIDENCE_CHAIN_INVALID",)

        # replay never actuates, tampered or not: state is unchanged
        untouched = await runtime.observe(episode.episode_id)
        assert untouched.state == {"x": 2}

        # live re-execution stays refused-by-default even against a tampered ledger
        refused_live = replay_ledger(ledger, mode=ReplayMode.LIVE_REEXECUTION)
        assert refused_live.valid is False
        assert refused_live.mismatches == ("LIVE_REEXECUTION_REFUSED",)
    finally:
        # restore so the ledger object is left in its real, valid state
        ledger._records[0] = original_record
    assert ledger.verify() is True
