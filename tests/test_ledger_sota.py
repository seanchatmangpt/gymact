from __future__ import annotations

import json
import sqlite3

import pytest

from gymact import MemoryReceiptLedger, Operation, Receipt, SQLiteReceiptLedger, Standing


def _receipt(receipt_id: str = "receipt-1") -> Receipt:
    return Receipt(
        receipt_id=receipt_id,
        episode_id="episode-1",
        operation=Operation.ACT,
        standing=Standing.ALIVE,
        subject_ref="urn:test:environment",
        capability_ref="urn:test:capability",
        idempotency_key="intent-1",
        pre_state_digest="0" * 64,
        post_state_digest="1" * 64,
    )


def test_memory_ledger_replay_is_idempotent_and_conflict_is_refused() -> None:
    ledger = MemoryReceiptLedger()
    receipt = _receipt()
    first = ledger.append(receipt)
    assert ledger.append(receipt) == first
    conflicting = receipt.model_copy(update={"reason": "different"})
    with pytest.raises(ValueError, match="RECEIPT_ID_CONFLICT"):
        ledger.append(conflicting)
    assert ledger.verify() is True
    assert len(ledger.records()) == 1


def test_memory_ledger_detects_captured_chain_mutation() -> None:
    ledger = MemoryReceiptLedger()
    ledger.append(_receipt())
    original = ledger.records()[0]
    ledger._records[0] = original.model_copy(update={"record_digest": "f" * 64})
    assert ledger.verify() is False


def test_sqlite_ledger_conflict_rolls_back_without_appending(tmp_path) -> None:
    ledger = SQLiteReceiptLedger(tmp_path / "ledger.sqlite3")
    try:
        receipt = _receipt()
        first = ledger.append(receipt)
        assert ledger.append(receipt) == first
        with pytest.raises(ValueError, match="RECEIPT_ID_CONFLICT"):
            ledger.append(receipt.model_copy(update={"reason": "different"}))
        assert ledger.verify() is True
        assert len(ledger.records()) == 1
    finally:
        ledger.close()


def test_memory_ledger_refuses_idempotency_key_reuse_with_different_intent() -> None:
    ledger = MemoryReceiptLedger()
    ledger.append(_receipt())
    different_intent = _receipt(receipt_id="receipt-2").model_copy(
        update={"capability_ref": "urn:test:a-different-capability"}
    )
    with pytest.raises(ValueError, match="IDEMPOTENCY_KEY_REUSE_WITH_DIFFERENT_INTENT"):
        ledger.append(different_intent)


def test_memory_ledger_admits_combinatorial_refinement_of_the_same_intent() -> None:
    """Mirrors cut.py's CombinatorialBRCEBroker: the same idempotency_key
    re-receipted with refined lineage/combinatorial-selection metadata is a
    legitimate refinement of the same intent, not a conflicting duplicate."""
    ledger = MemoryReceiptLedger()
    original = ledger.append(_receipt())
    refined = _receipt(receipt_id="receipt-2").model_copy(
        update={
            "parent_receipt_ids": (original.receipt.receipt_id,),
            "possibility_graph_digest": "graph-digest",
            "possibility_exploration_digest": "exploration-digest",
            "possibility_path_id": "path-id",
            "possibility_morphism_id": "do-id",
            "selection_digest": "selection-digest",
        }
    )
    record = ledger.append(refined)
    assert record.receipt.receipt_id == "receipt-2"
    assert len(ledger.records()) == 2


def test_sqlite_ledger_refuses_idempotency_key_reuse_with_different_intent(tmp_path) -> None:
    ledger = SQLiteReceiptLedger(tmp_path / "ledger.sqlite3")
    try:
        ledger.append(_receipt())
        different_intent = _receipt(receipt_id="receipt-2").model_copy(
            update={"capability_ref": "urn:test:a-different-capability"}
        )
        with pytest.raises(ValueError, match="IDEMPOTENCY_KEY_REUSE_WITH_DIFFERENT_INTENT"):
            ledger.append(different_intent)
        assert len(ledger.records()) == 1
    finally:
        ledger.close()


def test_sqlite_ledger_refuses_tampered_database_on_reopen(tmp_path) -> None:
    path = tmp_path / "tampered.sqlite3"
    ledger = SQLiteReceiptLedger(path)
    ledger.append(_receipt())
    ledger.close()

    connection = sqlite3.connect(path)
    row = connection.execute(
        "SELECT receipt_json FROM receipt_evidence WHERE sequence = 0"
    ).fetchone()
    assert row is not None
    payload = json.loads(row[0])
    payload["reason"] = "tampered"
    connection.execute(
        "UPDATE receipt_evidence SET receipt_json = ? WHERE sequence = 0",
        (json.dumps(payload, sort_keys=True, separators=(",", ":")),),
    )
    connection.commit()
    connection.close()

    with pytest.raises(ValueError, match="EVIDENCE_CHAIN_INVALID"):
        SQLiteReceiptLedger(path)
