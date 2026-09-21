"""End-to-end CLI contract test for `gymact reconcile`.

Exercises the real Typer CLI command (src/gymact/cli.py::reconcile) -- the
production entry point a caller actually invokes, not the underlying
`admit_retry` function directly -- against fixtures serialized from the
exact RETRY_ADMITTED-safe and NO_EFFECT-unsafe scenario values proven
correct in tests/test_action_contract.py::test_retry_requires_no_effect_and_safe_idempotency
(lines 171-189). This closes the gap where the ActionDefinition +
ReconciliationResult -> admit_retry JSON contract was exercised only via
direct Python calls, never through the CLI transport boundary a real
operator or script uses.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gymact.action_contract import (
    ActionDefinition,
    ReconciliationDisposition,
    ReconciliationResult,
    admit_retry,
)
from gymact.cli import app as cli_app
from gymact.models import Standing

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAFE_FIXTURE = FIXTURES_DIR / "cli_reconcile_request_safe.json"
UNSAFE_FIXTURE = FIXTURES_DIR / "cli_reconcile_request_unsafe.json"

runner = CliRunner()


def _invoke_reconcile(fixture: Path) -> dict[str, object]:
    result = runner.invoke(cli_app, ["reconcile", str(fixture)])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def _direct_admit_retry(fixture: Path) -> dict[str, object]:
    """Recompute admit_retry directly from the same fixture data, so the CLI's
    JSON output is checked against the real domain function's real output --
    not just against a hand-written expected dict."""
    data = json.loads(fixture.read_text(encoding="utf-8"))
    action = ActionDefinition.model_validate(data["action"])
    reconciliation = ReconciliationResult.model_validate(data["reconciliation"])
    return admit_retry(action, reconciliation).model_dump(mode="json")


def test_reconcile_cli_admits_retry_for_safe_idempotent_no_effect() -> None:
    payload = _invoke_reconcile(SAFE_FIXTURE)

    # Matches test_action_contract.py's `safe` assertions exactly.
    assert payload["retry_admitted"] is True
    assert payload["disposition"] == ReconciliationDisposition.RETRY_ADMITTED.value
    assert payload["standing"] == Standing.CANDIDATE.value
    assert payload["reason"] == "RETRY_CANDIDATE_ADMITTED_AUTHORITY_STILL_REQUIRED"
    assert payload["observed_state_digest"] == "state-a"
    assert payload["verification_ref"] == "verify-1"

    # The real CLI transport boundary must reproduce the real domain function's
    # output exactly -- no drift introduced by JSON (de)serialization.
    assert payload == _direct_admit_retry(SAFE_FIXTURE)


def test_reconcile_cli_refuses_retry_for_non_idempotent_no_effect() -> None:
    payload = _invoke_reconcile(UNSAFE_FIXTURE)

    # Matches test_action_contract.py's `unsafe` assertions exactly.
    assert payload["retry_admitted"] is False
    assert payload["reason"] == "UNSAFE_RETRY_REFUSED"
    assert payload["disposition"] == ReconciliationDisposition.RETRY_REFUSED.value
    assert payload["standing"] == Standing.REFUSED.value
    assert payload["observed_state_digest"] == "state-a"
    assert payload["verification_ref"] == "verify-1"

    assert payload == _direct_admit_retry(UNSAFE_FIXTURE)


def test_fixtures_isolate_idempotency_as_the_only_action_difference() -> None:
    """Structural guard: the safe/unsafe fixtures must differ only in the
    action's `idempotency` field, so a passing/failing test pair actually
    proves what it claims to prove."""
    safe_action = json.loads(SAFE_FIXTURE.read_text(encoding="utf-8"))["action"]
    unsafe_action = json.loads(UNSAFE_FIXTURE.read_text(encoding="utf-8"))["action"]

    diff_keys = {key for key in safe_action if safe_action[key] != unsafe_action.get(key)}
    assert diff_keys == {"idempotency"}
    assert safe_action["idempotency"] == "IDEMPOTENT"
    assert unsafe_action["idempotency"] == "UNKNOWN"

    safe_reconciliation = json.loads(SAFE_FIXTURE.read_text(encoding="utf-8"))["reconciliation"]
    unsafe_reconciliation = json.loads(UNSAFE_FIXTURE.read_text(encoding="utf-8"))["reconciliation"]
    assert safe_reconciliation == unsafe_reconciliation
    assert safe_reconciliation["disposition"] == "NO_EFFECT"
