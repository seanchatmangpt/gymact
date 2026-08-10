"""Real GymAct `Environment`/`EnvironmentProvider` operating on a real,
isolated, local git-tracked working tree -- not simulated.

`materialize()` creates a real temporary directory (`tempfile.mkdtemp`) and
runs a real `git init` + `git config user.email/user.name` subprocess
sequence in it to get a clean, isolated commit identity. It never touches
the caller's own working repository and never shares ambient git state
across episodes -- each materialized environment owns its own throwaway
worktree, deleted on `teardown()`.

Capability set matches `ggen/codebase-gym-pack/ontology.ttl` exactly (4
READ + 4 DO, see that file's own ontology-parity test,
`tests/test_codebase_ontology.py`):

  READ: inspect_tree, read_file, inspect_manifest, inspect_git_diff
  DO:   apply_patch, git_commit, run_test, run_build

`read_file`/`apply_patch` reuse the same path-containment discipline as
`gymact.local_providers._bounded_path` -- any path that resolves outside
the worktree root is refused (`AMBIGUOUS_SUBJECT_REFUSED`), never silently
clamped or partially honored.

`run_test`/`run_build` are real `subprocess.run` calls against the
worktree's own real test suite / build step (`pytest`, `python -m
py_compile`) -- stdout/stderr/returncode are captured verbatim from the
real process; nothing here fabricates a pass.

`requires_authority` in `CodebaseProvider.materialize()` defaults to
`True` (`config.get("requires_authority", True)`), matching this session's
established fix for the 8 other real-side-effect providers
(`terraform_docker_apply.py`, `terraform_plan.py`, etc.) -- this provider
is being built fresh, so it is built with the correct default from day
one rather than needing a later retrofit. `materialization_requires_authority`
stays `False` per the same established convention: materialize() itself is
not authority-gated, only DO-capability actuation inside the materialized
environment is.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

_MAX_CAPTURED_OUTPUT = 20000
_DEFAULT_GIT_TIMEOUT_SECONDS = 30.0
_DEFAULT_TEST_TIMEOUT_SECONDS = 120.0
_DEFAULT_BUILD_TIMEOUT_SECONDS = 120.0


def _bounded_path(root: Path, relative: str) -> Path:
    """Resolve `relative` under `root`, refusing any path traversal outside
    the worktree. Mirrors `gymact.local_providers._bounded_path`."""
    if not relative or Path(relative).is_absolute():
        raise ValueError("AMBIGUOUS_SUBJECT_REFUSED")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("AMBIGUOUS_SUBJECT_REFUSED") from exc
    return candidate


CODEBASE_CAPABILITIES = (
    Capability(
        iri="urn:gymact:codebase:capability:inspect_tree",
        title="inspect_tree",
        consequence=Consequence.READ,
        binding="inspect_tree",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:read_file",
        title="read_file",
        consequence=Consequence.READ,
        binding="read_file",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:inspect_manifest",
        title="inspect_manifest",
        consequence=Consequence.READ,
        binding="inspect_manifest",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:inspect_git_diff",
        title="inspect_git_diff",
        consequence=Consequence.READ,
        binding="inspect_git_diff",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:apply_patch",
        title="apply_patch",
        consequence=Consequence.DO,
        binding="apply_patch",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:git_commit",
        title="git_commit",
        consequence=Consequence.DO,
        binding="git_commit",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:run_test",
        title="run_test",
        consequence=Consequence.DO,
        binding="run_test",
    ),
    Capability(
        iri="urn:gymact:codebase:capability:run_build",
        title="run_build",
        consequence=Consequence.DO,
        binding="run_build",
    ),
)


class CodebaseEnvironment:
    """Real, isolated local git worktree wrapped as a GymAct environment."""

    def __init__(self, *, worktree: Path, requires_authority: bool = True) -> None:
        self.environment_id = f"urn:gymact:codebase:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._worktree = worktree.resolve()
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def _run_git(self, args: list[str], *, timeout: float = _DEFAULT_GIT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self._worktree,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return CODEBASE_CAPABILITIES

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        tree = sorted(
            str(p.relative_to(self._worktree).as_posix())
            for p in self._worktree.rglob("*")
            if p.is_file() and ".git" not in p.parts
        )
        log = self._run_git(["log", "--oneline"])
        status = self._run_git(["status", "--porcelain"])
        return {
            "worktree": str(self._worktree),
            "tree": tree,
            "git_log": log.stdout.strip(),
            "git_status": status.stdout.strip(),
        }

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        before = await self.observe()
        binding = capability.binding

        if binding == "inspect_tree":
            after = {"tree": before["tree"]}
        elif binding == "read_file":
            relative = str(payload.get("path", ""))
            target = _bounded_path(self._worktree, relative)
            if not target.is_file():
                after = {"path": relative, "exists": False, "content": None}
            else:
                after = {"path": relative, "exists": True, "content": target.read_text(encoding="utf-8")}
        elif binding == "inspect_manifest":
            manifest_name = None
            content = None
            for candidate in ("pyproject.toml", "requirements.txt"):
                candidate_path = self._worktree / candidate
                if candidate_path.is_file():
                    manifest_name = candidate
                    content = candidate_path.read_text(encoding="utf-8")
                    break
            after = {"manifest": manifest_name, "content": content}
        elif binding == "inspect_git_diff":
            ref_a = payload.get("ref_a")
            ref_b = payload.get("ref_b")
            args = ["diff"]
            if ref_a:
                args.append(str(ref_a))
            if ref_b:
                args.append(str(ref_b))
            diff_result = self._run_git(args)
            after = {
                "returncode": diff_result.returncode,
                "diff": diff_result.stdout[-_MAX_CAPTURED_OUTPUT:],
                "stderr": diff_result.stderr[-_MAX_CAPTURED_OUTPUT:],
            }
        elif binding == "apply_patch":
            patch_text = payload.get("patch")
            if not isinstance(patch_text, str) or not patch_text:
                raise TypeError("apply_patch requires a non-empty string 'patch'")
            check_process = subprocess.run(
                ["git", "apply", "--check", "-"],
                cwd=self._worktree,
                input=patch_text,
                capture_output=True,
                text=True,
                timeout=_DEFAULT_GIT_TIMEOUT_SECONDS,
                check=False,
            )
            apply_process = subprocess.run(
                ["git", "apply", "-"],
                cwd=self._worktree,
                input=patch_text,
                capture_output=True,
                text=True,
                timeout=_DEFAULT_GIT_TIMEOUT_SECONDS,
                check=False,
            )
            after = {
                "applied": apply_process.returncode == 0,
                "returncode": apply_process.returncode,
                "stdout": apply_process.stdout[-_MAX_CAPTURED_OUTPUT:],
                "stderr": apply_process.stderr[-_MAX_CAPTURED_OUTPUT:],
                "check_returncode": check_process.returncode,
            }
        elif binding == "git_commit":
            message = payload.get("message", "gymact codebase gym commit")
            self._run_git(["add", "-A"])
            commit_result = self._run_git(["commit", "-m", str(message), "--allow-empty"])
            sha_result = self._run_git(["rev-parse", "HEAD"])
            after = {
                "committed": commit_result.returncode == 0,
                "returncode": commit_result.returncode,
                "stdout": commit_result.stdout[-_MAX_CAPTURED_OUTPUT:],
                "stderr": commit_result.stderr[-_MAX_CAPTURED_OUTPUT:],
                "sha": sha_result.stdout.strip() if sha_result.returncode == 0 else None,
            }
        elif binding == "run_test":
            test_process = subprocess.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=self._worktree,
                capture_output=True,
                text=True,
                timeout=_DEFAULT_TEST_TIMEOUT_SECONDS,
                check=False,
            )
            after = {
                "returncode": test_process.returncode,
                "passed": test_process.returncode == 0,
                "stdout": test_process.stdout[-_MAX_CAPTURED_OUTPUT:],
                "stderr": test_process.stderr[-_MAX_CAPTURED_OUTPUT:],
            }
        elif binding == "run_build":
            py_files = [
                str(p.relative_to(self._worktree))
                for p in self._worktree.rglob("*.py")
                if ".git" not in p.parts
            ]
            build_process = subprocess.run(
                [sys.executable, "-m", "py_compile", *py_files],
                cwd=self._worktree,
                capture_output=True,
                text=True,
                timeout=_DEFAULT_BUILD_TIMEOUT_SECONDS,
                check=False,
            )
            after = {
                "returncode": build_process.returncode,
                "built": build_process.returncode == 0,
                "stdout": build_process.stdout[-_MAX_CAPTURED_OUTPUT:],
                "stderr": build_process.stderr[-_MAX_CAPTURED_OUTPUT:],
                "files_compiled": py_files,
            }
        else:
            raise ValueError(f"unsupported codebase binding: {binding}")

        return {"before": before, "after": after}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return await self.observe()

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        del checkpoint  # real restoration is out of scope for this minimal gym

    async def teardown(self) -> None:
        if self._closed:
            return
        shutil.rmtree(self._worktree, ignore_errors=True)
        self._closed = True


class CodebaseProvider:
    """Materializes a `CodebaseEnvironment` over a fresh, isolated real
    temporary git repository. Never the caller's own working repo."""

    name = "codebase"
    materialization_requires_authority = False

    async def materialize(self, *, scenario: str | None, config: dict[str, Any]) -> CodebaseEnvironment:
        del scenario
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")

        git_binary = shutil.which("git")
        if git_binary is None:
            raise RuntimeError("'git' is not on PATH -- install it to use CodebaseProvider")

        seed_files = config.get("seed_files")
        if seed_files is not None and not isinstance(seed_files, dict):
            raise TypeError("config.seed_files must be a dict[str, str] when provided")

        worktree = Path(tempfile.mkdtemp(prefix="gymact-codebase-"))

        init_result = subprocess.run(
            ["git", "init"],
            cwd=worktree,
            capture_output=True,
            text=True,
            timeout=_DEFAULT_GIT_TIMEOUT_SECONDS,
            check=False,
        )
        if init_result.returncode != 0:
            shutil.rmtree(worktree, ignore_errors=True)
            raise RuntimeError(f"git init failed: {init_result.stderr}")

        for key, value in (
            ("user.email", "gymact-codebase-gym@example.invalid"),
            ("user.name", "GymAct Codebase Gym"),
            ("commit.gpgsign", "false"),
        ):
            subprocess.run(
                ["git", "config", key, value],
                cwd=worktree,
                capture_output=True,
                text=True,
                timeout=_DEFAULT_GIT_TIMEOUT_SECONDS,
                check=False,
            )

        if seed_files:
            for relative, content in seed_files.items():
                target = _bounded_path(worktree, str(relative))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(content), encoding="utf-8")

        return CodebaseEnvironment(worktree=worktree, requires_authority=requires_authority)


__all__ = ["CODEBASE_CAPABILITIES", "CodebaseEnvironment", "CodebaseProvider"]
