"""Chicago-style contract test for the `gymact replay` CLI command.

Closes a real gap: every existing replay test (``tests/test_replay_crown.py``)
exercises ``gymact.replay.replay_ledger`` against a hand-rolled dataclass
``Ledger``/``Receipt`` pair, never the real ``SQLiteReceiptLedger`` file
backend, and never through the Typer CLI at all -- so the CLI's positional
``ledger`` path argument, its ``--mode`` option parsing, and its identity
``typer.Option`` flags (``--subject-ref``, ``--capability-ref``, ...) had zero
test coverage. This file appends real ``Receipt`` objects to a real
``SQLiteReceiptLedger`` backed by a file on disk, then drives the real
``replay`` Typer command through ``CliRunner.invoke`` exactly the way an
operator does from a shell, and asserts on the real JSON printed to stdout.

No test doubles anywhere in this file. The SQLite file, the receipt chain,
and the CLI process boundary (via Click's real argument parser) are all real
collaborators.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gymact import Operation, Receipt, SQLiteReceiptLedger, Standing
from gymact.cli import app as cli_app

_SUBJECT_REF = "urn:test:environment"
_CAPABILITY_REF = "urn:test:capability"
_POLICY_REVISION = "policy-rev-1"
_PRINCIPAL = "urn:test:agent"


def _receipt(
    receipt_id: str,
    *,
    parent_receipt_ids: tuple[str, ...] = (),
    idempotency_key: str,
) -> Receipt:
    return Receipt(
        receipt_id=receipt_id,
        episode_id="episode-cli-replay",
        operation=Operation.ACT,
        standing=Standing.ALIVE,
        subject_ref=_SUBJECT_REF,
        capability_ref=_CAPABILITY_REF,
        policy_revision=_POLICY_REVISION,
        principal=_PRINCIPAL,
        idempotency_key=idempotency_key,
        parent_receipt_ids=parent_receipt_ids,
        pre_state_digest="0" * 64,
        post_state_digest="1" * 64,
    )


def _build_real_ledger(path: Path) -> str:
    """Append two real, causally-chained receipts to a real SQLite file ledger.

    Returns the real ``record_digest`` of the chain head so the test can
    assert the CLI's reported ``head_digest`` against a value nothing but a
    real append computed.
    """
    ledger = SQLiteReceiptLedger(path)
    try:
        first = ledger.append(_receipt("receipt-1", idempotency_key="intent-1"))
        second = ledger.append(
            _receipt(
                "receipt-2",
                parent_receipt_ids=(first.receipt.receipt_id,),
                idempotency_key="intent-2",
            )
        )
    finally:
        ledger.close()
    return second.record_digest


def test_cli_replay_reports_real_evidence_replay_from_sqlite_file_ledger(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "cli-replay.sqlite3"
    head_digest = _build_real_ledger(ledger_path)

    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "replay",
            str(ledger_path),
            "--mode",
            "EVIDENCE_REPLAY",
            "--subject-ref",
            _SUBJECT_REF,
            "--capability-ref",
            _CAPABILITY_REF,
            "--policy-revision",
            _POLICY_REVISION,
            "--principal",
            _PRINCIPAL,
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)

    # Real replayed decision/effect identity: mode + validity of the actual
    # chain read back off disk, the real record count, and the real head
    # digest computed by SQLiteReceiptLedger.append (not re-derived here).
    assert payload["mode"] == "EVIDENCE_REPLAY"
    assert payload["valid"] is True
    assert payload["record_count"] == 2
    assert payload["head_digest"] == head_digest
    assert payload["mismatches"] == []
    assert payload["live_reexecution_admitted"] is False


def test_cli_replay_detects_real_identity_drift_via_typer_options(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "cli-replay-drift.sqlite3"
    ledger = SQLiteReceiptLedger(ledger_path)
    try:
        ledger.append(_receipt("receipt-1", idempotency_key="intent-1"))
    finally:
        ledger.close()

    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "replay",
            str(ledger_path),
            "--mode",
            "EVIDENCE_REPLAY",
            "--subject-ref",
            "urn:test:a-different-environment",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert payload["mismatches"] == ["SUBJECT_REF_DRIFT"]
    assert payload["record_count"] == 1


def test_cli_replay_refuses_unknown_mode_via_real_typer_parsing(tmp_path: Path) -> None:
    ledger_path = tmp_path / "cli-replay-badmode.sqlite3"
    ledger = SQLiteReceiptLedger(ledger_path)
    ledger.close()

    runner = CliRunner()
    result = runner.invoke(cli_app, ["replay", str(ledger_path), "--mode", "NOT_A_MODE"])

    # Typer/Click's real BadParameter usage-error exit code, raised by the
    # real `ReplayMode(mode)` conversion inside the `replay` command body --
    # never reached the ledger read, confirming --mode is really parsed and
    # validated by the CLI layer itself, not merely accepted as free text.
    assert result.exit_code == 2
    assert "unknown replay mode" in result.stderr.lower()
