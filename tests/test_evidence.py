from __future__ import annotations

import pytest
from rdflib import RDF, URIRef

from gymact.evidence import (
    EARL,
    PROV,
    SOSA,
    MemoryReceiptLedger,
    SQLiteReceiptLedger,
    receipts_to_prov,
    verification_to_earl,
    verify_receipt_chain,
)
from gymact.models import Operation, Receipt, ReceiptStage, Standing, VerificationResult


@pytest.mark.asyncio
async def test_memory_receipt_ledger_is_blake3_chained_and_filterable() -> None:
    ledger = MemoryReceiptLedger()
    first = await ledger.append(
        Receipt(
            episode_id="episode-a",
            operation=Operation.ACT,
            stage=ReceiptStage.PREPARED,
            standing=Standing.PARTIAL_ALIVE,
            subject_ref="urn:test:world",
            capability_ref="urn:test:capability",
            reason="ACTUATION_PREPARED",
        )
    )
    second = await ledger.append(
        Receipt(
            episode_id="episode-a",
            operation=Operation.ACT,
            standing=Standing.ALIVE,
            subject_ref="urn:test:world",
            capability_ref="urn:test:capability",
            prepared_receipt_digest=first.receipt_digest,
            reason="CONSEQUENCE_OBSERVED",
        )
    )
    third = await ledger.append(
        Receipt(
            episode_id="episode-b",
            operation=Operation.VERIFY,
            standing=Standing.ALIVE,
            capability_ref="urn:gymact:operation:verify",
            reason="VERIFICATION_PASSED",
        )
    )

    assert first.receipt_digest is not None
    assert second.previous_receipt_digest == first.receipt_digest
    assert third.previous_receipt_digest == second.receipt_digest
    assert len(first.receipt_digest) == 64
    assert await ledger.verify_chain() is True
    assert await ledger.receipts("episode-a") == (first, second)


def test_receipt_chain_detects_tampering() -> None:
    forged = Receipt(
        episode_id="episode",
        operation=Operation.ACT,
        standing=Standing.ALIVE,
        receipt_digest="0" * 64,
    )
    assert verify_receipt_chain((forged,)) is False


@pytest.mark.asyncio
async def test_sqlite_receipt_ledger_reopens_and_verifies(tmp_path) -> None:
    path = tmp_path / "receipts.sqlite3"
    ledger = SQLiteReceiptLedger(path)
    first = await ledger.append(
        Receipt(
            episode_id="persistent",
            operation=Operation.MATERIALIZE,
            stage=ReceiptStage.PREPARED,
            standing=Standing.PARTIAL_ALIVE,
            capability_ref="urn:gymact:operation:materialize",
            reason="ACTUATION_PREPARED",
        )
    )
    await ledger.append(
        Receipt(
            episode_id="persistent",
            operation=Operation.MATERIALIZE,
            standing=Standing.ALIVE,
            capability_ref="urn:gymact:operation:materialize",
            prepared_receipt_digest=first.receipt_digest,
            reason="MATERIALIZATION_OBSERVED",
        )
    )

    reopened = SQLiteReceiptLedger(path)
    receipts = await reopened.receipts("persistent")
    assert len(receipts) == 2
    assert receipts[1].prepared_receipt_digest == first.receipt_digest
    assert await reopened.verify_chain() is True


@pytest.mark.asyncio
async def test_prov_projection_keeps_actuation_procedure_and_state_evidence() -> None:
    ledger = MemoryReceiptLedger()
    receipt = await ledger.append(
        Receipt(
            episode_id="prov-episode",
            operation=Operation.ACT,
            standing=Standing.ALIVE,
            subject_ref="urn:test:world",
            capability_ref="urn:test:procedure",
            pre_state_digest="a" * 64,
            post_state_digest="b" * 64,
            reason="CONSEQUENCE_OBSERVED",
        )
    )
    graph = receipts_to_prov((receipt,))
    activity = URIRef(f"urn:gymact:activity:{receipt.receipt_id}")
    receipt_uri = URIRef(f"urn:gymact:receipt:{receipt.receipt_id}")
    assert (activity, RDF.type, SOSA.Actuation) in graph
    assert (activity, SOSA.usedProcedure, URIRef("urn:test:procedure")) in graph
    assert (receipt_uri, PROV.wasGeneratedBy, activity) in graph


def test_earl_projection_distinguishes_verification_outcome() -> None:
    passed = VerificationResult(
        episode_id="earl-episode",
        passed=True,
        expected={"healthy": True},
        observed={"healthy": True},
        state_digest="c" * 64,
    )
    failed = passed.model_copy(
        update={"verification_id": "failed-verification", "passed": False}
    )
    passed_graph = verification_to_earl(passed)
    failed_graph = verification_to_earl(failed)
    assert (None, EARL.outcome, EARL.passed) in passed_graph
    assert (None, EARL.outcome, EARL.failed) in failed_graph
