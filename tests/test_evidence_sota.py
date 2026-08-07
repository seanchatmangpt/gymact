from __future__ import annotations

import math

import pytest
from blake3 import blake3
from pydantic import ValidationError

from gymact import (
    ActuationIntent,
    GymAct,
    MaterializationIntent,
    MemoryProvider,
    SQLiteReceiptLedger,
    Standing,
    build_contract,
    export_manufacturing_bundle,
)
from gymact.evidence import canonical_bytes
from gymact.providers import MemoryEnvironment


def test_rfc8785_canonicalization_is_key_order_independent() -> None:
    assert canonical_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert canonical_bytes({"a": 2, "b": 1}) == canonical_bytes({"b": 1, "a": 2})


def test_blake3_dependency_matches_known_empty_input_vector() -> None:
    assert blake3(b"").hexdigest() == (
        "af1349b9f5f9a1a6a0404dea36dcc949"
        "9bcb25c9adc112b7cc9a93cae41f3262"
    )


def test_non_finite_intent_is_rejected_before_runtime() -> None:
    with pytest.raises(ValidationError, match="INPUT_NOT_RFC8785_CANONICAL"):
        ActuationIntent(
            episode_id="episode",
            capability="urn:test:capability",
            payload={"value": math.nan},
        )


def test_runtime_contract_recomputes_its_own_digest() -> None:
    contract = build_contract()
    assert contract.canonicalization == "RFC8785-JCS"
    assert contract.verify_digest() is True
    assert "http://www.w3.org/ns/prov#" in contract.public_semantics
    assert "http://www.w3.org/ns/earl#" in contract.public_semantics


def test_manufacturing_bundle_is_canonical_and_complete(tmp_path) -> None:
    exported = export_manufacturing_bundle(tmp_path)
    assert set(exported) == {
        "profile.ttl",
        "profile.shacl.ttl",
        "runtime-contract.jcs.json",
    }
    payload = (tmp_path / "runtime-contract.jcs.json").read_bytes()
    assert payload == canonical_bytes(build_contract().model_dump(mode="json"))


class _NonCanonicalStateEnvironment(MemoryEnvironment):
    async def observe(self):  # type: ignore[no-untyped-def]
        return {"value": math.nan}


class _NonCanonicalStateProvider(MemoryProvider):
    name = "noncanonical-state"

    async def materialize(self, *, scenario, config):  # type: ignore[no-untyped-def]
        del scenario, config
        return _NonCanonicalStateEnvironment()


@pytest.mark.asyncio
async def test_noncanonical_provider_state_is_typed_blocked() -> None:
    runtime = GymAct()
    runtime.register_provider(_NonCanonicalStateProvider())
    result = await runtime.materialize(
        MaterializationIntent(
            provider="noncanonical-state",
            idempotency_key="noncanonical-state",
        )
    )
    assert result.standing == Standing.BLOCKED
    assert result.receipt.reason == "STATE_NOT_RFC8785_CANONICAL"


@pytest.mark.asyncio
async def test_sqlite_receipt_ledger_survives_reopen(tmp_path) -> None:
    path = tmp_path / "evidence.sqlite3"
    ledger = SQLiteReceiptLedger(path)
    runtime = GymAct(receipt_ledger=ledger)
    runtime.register_provider(MemoryProvider())
    result = await runtime.materialize(
        MaterializationIntent(provider="memory", idempotency_key="sqlite-materialize")
    )
    assert result.accepted is True
    receipt_id = result.receipt.receipt_id
    assert ledger.verify() is True
    assert ledger.find(receipt_id) is not None
    ledger.close()

    reopened = SQLiteReceiptLedger(path)
    try:
        assert reopened.verify() is True
        assert len(reopened.records()) == 1
        assert reopened.find(receipt_id) is not None
    finally:
        reopened.close()
