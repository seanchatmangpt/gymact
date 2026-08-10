"""First-class GymAct provider for the real upstream SREGym benchmark.

This integration deliberately wraps SREGym's own CLI and result artifacts instead of
reimplementing its conductor, fault injectors, MCP tools, or oracles.  The upstream
checkout remains the semantic/execution authority for SRE problem definition and
scoring; GymAct supplies bounded admission, authority, receipts, verification, and
replay around that execution.

Upstream compatibility baseline:
    SREGym/SREGym @ ba07faf1a322f9b6d4a279643bb796aa2f36f64b

The provider is dependency-light on purpose: SREGym has a large, fast-moving runtime
stack and owns its own ``uv`` environment.  GymAct launches ``uv run python main.py``
in an explicitly supplied SREGym checkout.  This prevents GymAct's package graph from
silently becoming SREGym's package graph and makes the exact upstream revision part of
the admitted subject.

Consequence law is preserved: a successful process exit is *not* a solved benchmark.
The provider parses SREGym's own CSV fields ``Diagnosis.success`` and
``Mitigation.success`` independently and derives ``solved`` only from the benchmark
stages that SREGym actually emitted.  Deployment failure and timeout are surfaced
separately.  The environment requires authority for every run because SREGym mutates a
live Kubernetes world through its own conductor/fault injectors.
"""

from __future__ import annotations

import csv
import os
import shutil
import time
from copy import deepcopy
from pathlib import Path
from subprocess import PIPE
from typing import Any
from uuid import uuid4

import anyio

from gymact.models import Capability, Consequence

SREGYM_UPSTREAM_REPOSITORY = "SREGym/SREGym"
SREGYM_COMPAT_REVISION = "ba07faf1a322f9b6d4a279643bb796aa2f36f64b"

SREGYM_RUN_CAPABILITY = Capability(
    iri="urn:gymact:sregym:capability:run",
    title="Run the real SREGym conductor against an admitted problem or suite",
    consequence=Consequence.DO,
    binding="run",
)

_REQUIRED_BINARIES = ("git", "uv", "docker", "kubectl", "helm")


def _boolish(value: object) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _latest_result_csv(root: Path, agent: str, started_at: float) -> Path | None:
    results_root = root / "results"
    if not results_root.exists():
        return None
    candidates = [
        path
        for path in results_root.rglob(f"{agent}_ALL_results.csv")
        if path.is_file() and path.stat().st_mtime >= started_at - 2.0
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def _read_result_csv(path: Path) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("SREGYM_RESULT_EMPTY")

    normalized: list[dict[str, Any]] = []
    for raw in rows:
        diagnosis = _boolish(raw.get("Diagnosis.success"))
        mitigation = _boolish(raw.get("Mitigation.success"))
        deploy_failed = _boolish(raw.get("deploy_failed")) is True
        timed_out = _boolish(raw.get("timed_out")) is True
        stage_values = [value for value in (diagnosis, mitigation) if value is not None]
        solved = bool(stage_values) and all(stage_values) and not deploy_failed and not timed_out
        normalized.append(
            {
                "problem_id": raw.get("problem_id"),
                "attempt": raw.get("attempt"),
                "diagnosis_success": diagnosis,
                "mitigation_success": mitigation,
                "deploy_failed": deploy_failed,
                "timed_out": timed_out,
                "ttl_seconds": raw.get("TTL"),
                "ttm_seconds": raw.get("TTM"),
                "solved": solved,
            }
        )

    return {
        "rows": normalized,
        "attempts": len(normalized),
        "solved_attempts": sum(1 for row in normalized if row["solved"]),
        "all_solved": bool(normalized) and all(row["solved"] for row in normalized),
    }


async def _git_head(root: Path) -> str:
    result = await anyio.run_process(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        stdout=PIPE,
        stderr=PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("SREGYM_GIT_HEAD_UNAVAILABLE")
    return result.stdout.decode().strip()


class SREGymEnvironment:
    """One admitted SREGym checkout/problem-or-suite execution subject."""

    def __init__(
        self,
        *,
        root: Path,
        upstream_revision: str,
        problem: str | None,
        suite: str | None,
        agent: str,
        model: str,
        judge_model: str | None,
        noise: bool,
        n_attempts: int,
        agent_timeout: int,
        reasoning_effort: str | None,
        env: dict[str, str],
    ) -> None:
        self.environment_id = f"urn:gymact:sregym:environment:{uuid4().hex}"
        self.requires_authority = True
        self._root = root
        self._upstream_revision = upstream_revision
        self._problem = problem
        self._suite = suite
        self._agent = agent
        self._model = model
        self._judge_model = judge_model
        self._noise = noise
        self._n_attempts = n_attempts
        self._agent_timeout = agent_timeout
        self._reasoning_effort = reasoning_effort
        self._env = env
        self._closed = False
        self._state: dict[str, Any] = {
            "upstream_repository": SREGYM_UPSTREAM_REPOSITORY,
            "upstream_revision": upstream_revision,
            "problem": problem,
            "suite": suite,
            "agent": agent,
            "model": model,
            "judge_model": judge_model,
            "noise": noise,
            "n_attempts": n_attempts,
            "attempted": False,
            "process_returncode": None,
            "result_csv": None,
            "diagnosis_success": None,
            "mitigation_success": None,
            "solved": False,
            "native_results": None,
        }

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return (SREGYM_RUN_CAPABILITY,)

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return deepcopy(self._state)

    def _command(self) -> list[str]:
        command = [
            "uv",
            "run",
            "python",
            "main.py",
            "--agent",
            self._agent,
            "--model",
            self._model,
            "--n-attempts",
            str(self._n_attempts),
            "--agent-timeout",
            str(self._agent_timeout),
        ]
        if self._problem is not None:
            command += ["--problem", self._problem]
        elif self._suite is not None:
            command += ["--suite", self._suite]
        if self._judge_model is not None:
            command += ["--judge-model", self._judge_model]
        if self._reasoning_effort is not None:
            command += ["--reasoning-effort", self._reasoning_effort]
        if self._noise:
            command.append("--noise")
        return command

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        if capability.binding != "run":
            raise ValueError(f"unsupported sregym binding: {capability.binding}")
        if payload:
            raise ValueError("SREGYM_RUN_PAYLOAD_MUST_BE_EMPTY; configure the admitted environment instead")

        before = deepcopy(self._state)
        started_at = time.time()
        process_env = dict(os.environ)
        process_env.update(self._env)
        command = self._command()
        result = await anyio.run_process(
            command,
            cwd=str(self._root),
            env=process_env,
            stdout=PIPE,
            stderr=PIPE,
            check=False,
        )
        result_csv = _latest_result_csv(self._root, self._agent, started_at)
        native_results = _read_result_csv(result_csv) if result_csv is not None else None

        diagnosis_values = (
            [row["diagnosis_success"] for row in native_results["rows"] if row["diagnosis_success"] is not None]
            if native_results
            else []
        )
        mitigation_values = (
            [row["mitigation_success"] for row in native_results["rows"] if row["mitigation_success"] is not None]
            if native_results
            else []
        )
        solved = bool(native_results) and native_results["all_solved"] and result.returncode == 0
        self._state = {
            **self._state,
            "attempted": True,
            "process_returncode": result.returncode,
            "result_csv": str(result_csv) if result_csv is not None else None,
            "diagnosis_success": all(diagnosis_values) if diagnosis_values else None,
            "mitigation_success": all(mitigation_values) if mitigation_values else None,
            "solved": solved,
            "native_results": native_results,
            "stdout_tail": result.stdout.decode(errors="replace")[-4000:],
            "stderr_tail": result.stderr.decode(errors="replace")[-4000:],
        }
        if result.returncode != 0:
            raise RuntimeError(f"SREGYM_PROCESS_FAILED:{result.returncode}")
        if result_csv is None:
            raise RuntimeError("SREGYM_RESULT_ARTIFACT_NOT_FOUND")
        return {"before": before, "after": deepcopy(self._state), "command": command}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        return all(observed.get(key) == value for key, value in expected.items()), observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        # This is an evidence checkpoint only.  SREGym owns Kubernetes rollback/cleanup.
        return {"restorable": not self._state["attempted"], "state": deepcopy(self._state)}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        if checkpoint.get("restorable") is not True:
            raise RuntimeError("SREGYM_EXTERNAL_WORLD_RESTORE_UNSUPPORTED")
        state = checkpoint.get("state")
        if not isinstance(state, dict):
            raise TypeError("checkpoint.state must be an object")
        self._state = deepcopy(state)

    async def teardown(self) -> None:
        self._closed = True


class SREGymProvider:
    """Materialize an exact-revision SREGym subject without actuating it."""

    name = "sregym"
    materialization_requires_authority = False

    async def materialize(self, *, scenario: str | None, config: dict[str, Any]) -> SREGymEnvironment:
        root_value = config.get("root") or os.environ.get("SREGYM_ROOT")
        if not isinstance(root_value, str) or not root_value:
            raise ValueError("SREGYM_ROOT_REQUIRED")
        root = Path(root_value).expanduser().resolve()
        if not (root / "main.py").is_file() or not (root / "pyproject.toml").is_file():
            raise RuntimeError("SREGYM_CHECKOUT_INVALID")

        suite = config.get("suite")
        if suite is not None and (not isinstance(suite, str) or not suite):
            raise TypeError("config.suite must be a non-empty string")
        if scenario is not None and suite is not None:
            raise ValueError("SREGYM_PROBLEM_AND_SUITE_ARE_MUTUALLY_EXCLUSIVE")
        if scenario is None and suite is None:
            suite = "sregym-lite"

        for binary in _REQUIRED_BINARIES:
            if shutil.which(binary) is None:
                raise RuntimeError(f"SREGYM_DEPENDENCY_MISSING:{binary}")

        actual_revision = await _git_head(root)
        expected_revision = config.get("expected_revision", SREGYM_COMPAT_REVISION)
        if not isinstance(expected_revision, str) or not expected_revision:
            raise TypeError("config.expected_revision must be a non-empty string")
        allow_revision_mismatch = config.get("allow_revision_mismatch", False)
        if not isinstance(allow_revision_mismatch, bool):
            raise TypeError("config.allow_revision_mismatch must be a boolean")
        if actual_revision != expected_revision and not allow_revision_mismatch:
            raise RuntimeError(
                f"SREGYM_REVISION_MISMATCH:expected={expected_revision}:actual={actual_revision}"
            )

        agent = config.get("agent", "stratus")
        model = config.get("model", "gpt-5")
        judge_model = config.get("judge_model")
        reasoning_effort = config.get("reasoning_effort")
        for field, value in (("agent", agent), ("model", model)):
            if not isinstance(value, str) or not value:
                raise TypeError(f"config.{field} must be a non-empty string")
        if judge_model is not None and (not isinstance(judge_model, str) or not judge_model):
            raise TypeError("config.judge_model must be a non-empty string when supplied")
        if reasoning_effort is not None and not isinstance(reasoning_effort, str):
            raise TypeError("config.reasoning_effort must be a string when supplied")

        noise = config.get("noise", False)
        if not isinstance(noise, bool):
            raise TypeError("config.noise must be a boolean")
        n_attempts = config.get("n_attempts", 1)
        if not isinstance(n_attempts, int) or isinstance(n_attempts, bool) or n_attempts < 1:
            raise TypeError("config.n_attempts must be a positive integer")
        agent_timeout = config.get("agent_timeout", 1800)
        if not isinstance(agent_timeout, int) or isinstance(agent_timeout, bool) or agent_timeout < 1:
            raise TypeError("config.agent_timeout must be a positive integer")

        extra_env = config.get("env", {})
        if not isinstance(extra_env, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in extra_env.items()
        ):
            raise TypeError("config.env must be an object of string values")

        return SREGymEnvironment(
            root=root,
            upstream_revision=actual_revision,
            problem=scenario,
            suite=suite,
            agent=agent,
            model=model,
            judge_model=judge_model,
            noise=noise,
            n_attempts=n_attempts,
            agent_timeout=agent_timeout,
            reasoning_effort=reasoning_effort,
            env=dict(extra_env),
        )


__all__ = [
    "SREGYM_COMPAT_REVISION",
    "SREGYM_RUN_CAPABILITY",
    "SREGYM_UPSTREAM_REPOSITORY",
    "SREGymEnvironment",
    "SREGymProvider",
]
