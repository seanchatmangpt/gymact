from __future__ import annotations

import pytest

from gymact import GymAct, MaterializationIntent, MemoryProvider, SQLiteReceiptLedger, build_contract
from gymact.evidence import canonical_bytes


def test_rfc8785_canonicalization_is_key_order_independent() -> None:
    assert canonical_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert canonical_bytes({"a": 2, "b": 1}) == canonical_bytes({"b": 1, "a": 2})


def test_runtime_contract_recomputes_its_own_digest() -> None:
    contract = build_contract()
    assert contract.canonicalization == "RFC8785-JCS"
    assert contract.verify_digest() is True
    assert "http://www.w3.org/ns/prov#" in contract.public_semantics
    assert "http://www.w3.org/ns/earl#" in contract.public_semantics


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
