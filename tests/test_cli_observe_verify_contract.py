"""Real CliRunner coverage for the `gymact observe` / `gymact verify` JSON contract.

Closes a gap where the CLI's observe/verify JSON contract was only exercised
via internal `_materialize_request` Python calls (see
`tests/test_cli_dcm_authority.py`), never through the real CLI
subprocess-equivalent path (`typer.testing.CliRunner`, the same pattern
`tests/test_core.py::test_typer_cli_version_profile_export_and_demo` already
uses for `version`/`validate-profile`/`export-profile`/`demo`). This module
invokes the real `observe` and `verify` Typer commands against a fixture on
disk and asserts on the real JSON stdout -- no `_materialize_request` call in
this file, no mock of any kind.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gymact.cli import app as cli_app

FIXTURE = Path(__file__).parent / "fixtures" / "cli_observe_verify_request.json"


def test_cli_observe_reports_real_state_digest() -> None:
    runner = CliRunner()
    result = runner.invoke(cli_app, ["observe", str(FIXTURE)])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    observation = payload["observation"]
    assert isinstance(observation["state_digest"], str)
    assert observation["state_digest"] != ""
    assert observation["state"] == {"x": 1}


def test_cli_verify_reports_real_passed_true() -> None:
    runner = CliRunner()
    result = runner.invoke(cli_app, ["verify", str(FIXTURE)])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    verification = payload["verification"]
    assert verification["passed"] is True
    assert verification["expected"] == {"x": 1}
    assert isinstance(verification["state_digest"], str)
    assert verification["state_digest"] != ""


def test_cli_verify_reports_real_passed_false_on_mismatch(tmp_path: Path) -> None:
    mismatched = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mismatched["expected"] = {"x": 999}
    mismatched["materialization_idempotency_key"] = "cli-observe-verify-mismatch"
    request_path = tmp_path / "mismatch.json"
    request_path.write_text(json.dumps(mismatched), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli_app, ["verify", str(request_path)])

    assert result.exit_code == 0, result.stdout
    verification = json.loads(result.stdout)["verification"]
    assert verification["passed"] is False
