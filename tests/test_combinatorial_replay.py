from __future__ import annotations

from gymact.evidence import MemoryReceiptLedger
from gymact.models import Operation, Receipt, Standing
from gymact.replay import ReplayExpectation, replay_ledger


def receipt() -> Receipt:
    return Receipt(
        receipt_id="receipt-1",
        episode_id="episode",
        operation=Operation.VERIFY,
        standing=Standing.ALIVE,
        subject_ref="urn:subject:1",
        capability_ref="urn:capability:1",
        possibility_graph_digest="graph-1",
        possibility_path_id="path-1",
        possibility_morphism_id="do-1",
        selection_digest="selection-1",
        selection_basis_refs=("urn:evidence:1",),
        verified=True,
    )


def test_replay_accepts_exact_combinatorial_identity() -> None:
    ledger = MemoryReceiptLedger()
    ledger.append(receipt())
    report = replay_ledger(
        ledger,
        expected=ReplayExpectation(
            subject_ref="urn:subject:1",
            capability_ref="urn:capability:1",
            possibility_graph_digest="graph-1",
            possibility_path_id="path-1",
            possibility_morphism_id="do-1",
            selection_digest="selection-1",
        ),
    )
    assert report.valid
    assert report.mismatches == ()


def test_replay_detects_graph_path_morphism_and_selection_drift() -> None:
    ledger = MemoryReceiptLedger()
    ledger.append(receipt())
    report = replay_ledger(
        ledger,
        expected=ReplayExpectation(
            possibility_graph_digest="graph-2",
            possibility_path_id="path-2",
            possibility_morphism_id="do-2",
            selection_digest="selection-2",
        ),
    )
    assert not report.valid
    assert set(report.mismatches) == {
        "POSSIBILITY_GRAPH_DIGEST_DRIFT",
        "POSSIBILITY_PATH_ID_DRIFT",
        "POSSIBILITY_MORPHISM_ID_DRIFT",
        "SELECTION_DIGEST_DRIFT",
    }
