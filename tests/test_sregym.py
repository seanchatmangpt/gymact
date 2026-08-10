"""Contract tests for the first-class SREGym provider.

These tests intentionally do not manufacture a fake Kubernetes/SREGym run. They cover
the GymAct-owned boundary only: exact native-result interpretation, command projection,
authority classification, checkpoint semantics, and verification. A real SREGym episode
remains a separate standing and is validated with the procedure in
``docs/integrations/sregym.md``.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from gymact.gyms.sregym import (
    SREGYM_COMPAT_REVISION,
    SREGYM_RUN_CAPABILITY,
    SREGymEnvironment,
    SREGymProvider,
    _boolish,
    _read_result_csv,
)
from gymact.models import Consequence
from gymact.registry import builtin_capabilities, builtin_provider_names, create_builtin_provider
from gymact.semantic import ProfileAuthority


def _environment(tmp_path: Path, **overrides) -> SREGymEnvironment:
    values = {
        "root": tmp_path,
        "upstream_revision": SREGYM_COMPAT_REVISION,
        "problem": "target_port",
        "suite": None,
        "agent": "stratus",
        "model": "gpt-5",
        "judge_model": None,
        "noise": False,
        "n_attempts": 1,
        "agent_timeout": 1800,
        "reasoning_effort": None,
        "env": {},
    }
    values.update(overrides)
    return SREGymEnvironment(**values)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_sregym_is_a_first_class_builtin_provider() -> None:
    assert "sregym" in builtin_provider_names()
    assert builtin_capabilities("sregym") == (SREGYM_RUN_CAPABILITY,)
    assert isinstance(create_builtin_provider("sregym"), SREGymProvider)


def test_sregym_capability_is_admitted_by_public_semantic_profile() -> None:
    result = ProfileAuthority().validate_capabilities((SREGYM_RUN_CAPABILITY,))
    assert result.conforms is True, result.report_text


def test_sregym_run_is_a_do_capability_and_environment_requires_authority(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    assert SREGYM_RUN_CAPABILITY.consequence == Consequence.DO
    assert env.requires_authority is True
    assert env.capabilities() == (SREGYM_RUN_CAPABILITY,)


def test_native_result_keeps_diagnosis_and_mitigation_distinct(tmp_path: Path) -> None:
    path = tmp_path / "result.csv"
    _write_csv(
        path,
        [
            {
                "problem_id": "target_port",
                "attempt": "1",
                "Diagnosis.success": "True",
                "Mitigation.success": "False",
                "TTL": "12.5",
                "TTM": "30.0",
            }
        ],
    )
    result = _read_result_csv(path)
    row = result["rows"][0]
    assert row["diagnosis_success"] is True
    assert row["mitigation_success"] is False
    assert row["solved"] is False
    assert result["all_solved"] is False


def test_native_result_marks_both_successful_stages_solved(tmp_path: Path) -> None:
    path = tmp_path / "result.csv"
    _write_csv(
        path,
        [
            {
                "problem_id": "target_port",
                "attempt": "1",
                "Diagnosis.success": "true",
                "Mitigation.success": "true",
            }
        ],
    )
    result = _read_result_csv(path)
    assert result["solved_attempts"] == 1
    assert result["all_solved"] is True


def test_native_result_never_crowns_a_deploy_failure(tmp_path: Path) -> None:
    path = tmp_path / "result.csv"
    _write_csv(
        path,
        [
            {
                "problem_id": "target_port",
                "attempt": "1",
                "Diagnosis.success": "true",
                "Mitigation.success": "true",
                "deploy_failed": "true",
            }
        ],
    )
    assert _read_result_csv(path)["all_solved"] is False


def test_command_projects_real_upstream_single_problem_cli(tmp_path: Path) -> None:
    env = _environment(
        tmp_path,
        agent="codex",
        model="gpt-5.4",
        judge_model="anthropic/claude-sonnet-4-6",
        noise=True,
        n_attempts=2,
        reasoning_effort="high",
    )
    command = env._command()
    problem_index = command.index("--problem")
    assert command[:4] == ["uv", "run", "python", "main.py"]
    assert command[problem_index : problem_index + 2] == ["--problem", "target_port"]
    assert "--noise" in command
    assert command[command.index("--n-attempts") + 1] == "2"
    assert command[command.index("--reasoning-effort") + 1] == "high"


def test_command_projects_real_upstream_lite_suite_cli(tmp_path: Path) -> None:
    env = _environment(tmp_path, problem=None, suite="sregym-lite")
    command = env._command()
    suite_index = command.index("--suite")
    assert command[suite_index : suite_index + 2] == ["--suite", "sregym-lite"]
    assert "--problem" not in command


async def test_observe_verify_and_pre_actuation_checkpoint_are_consistent(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    observed = await env.observe()
    assert observed["attempted"] is False
    assert observed["solved"] is False
    passed, verified = await env.verify({"upstream_revision": SREGYM_COMPAT_REVISION})
    assert passed is True
    assert verified == observed
    checkpoint = await env.checkpoint()
    assert checkpoint["restorable"] is True
    await env.restore(checkpoint)
    assert await env.observe() == observed


async def test_external_world_checkpoint_cannot_claim_restore_after_actuation(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    env._state["attempted"] = True
    checkpoint = await env.checkpoint()
    assert checkpoint["restorable"] is False
    with pytest.raises(RuntimeError, match="SREGYM_EXTERNAL_WORLD_RESTORE_UNSUPPORTED"):
        await env.restore(checkpoint)


def test_boolish_refuses_unknown_text() -> None:
    assert _boolish("success") is None
    assert _boolish("") is None
