"""Real GymAct `Environment`/`EnvironmentProvider` operating on a real,
isolated, local git-tracked working tree -- not simulated.

`materialize()` normally creates a real temporary directory
(`tempfile.mkdtemp`) and runs a real `git init` + `git config
user.email/user.name` subprocess sequence in it to get a clean, isolated
commit identity. It never touches the caller's own working repository and
never shares ambient git state across episodes -- each materialized
environment owns its own throwaway worktree, deleted on `teardown()`.
Alternatively, passing `config["clone_source"]` + `config["clone_sha"]`
routes materialize() through the real `clone_at_ref()` primitive below,
producing a worktree pinned at an EXACT real commit of a real repo (local
path or remote URL) instead of an empty from-scratch repo.

Capability set matches `ggen/codebase-gym-pack/ontology.ttl` exactly (4
READ + 4 DO, see that file's own ontology-parity test,
`tests/test_codebase_ontology.py`):

  READ: inspect_tree, read_file, inspect_manifest, inspect_git_diff
  DO:   apply_patch, git_commit, run_test, run_build

`read_file`/`apply_patch` reuse the same path-containment discipline as
`gymact.local_providers._bounded_path` -- any path that resolves outside
the worktree root is refused (`AMBIGUOUS_SUBJECT_REFUSED`), never silently
clamped or partially honored.

`run_test`/`run_build` dispatch to the REAL matching toolchain command for
the worktree's detected `ProjectKind` (see `detect_project_kind()`):
`pytest`/`py_compile` for python, `cargo test`/`cargo build` for rust,
`mix test`/`mix compile` for elixir, `npm`/`pnpm install` + `test`/`run
build` for node, `go test`/`go build` for go -- stdout/stderr/returncode
are captured verbatim from the real process for every kind; nothing here
fabricates a pass. A payload `{"kind": "<project-kind>"}` override lets a
caller disambiguate a MIXED-manifest worktree explicitly instead of
guessing.

`requires_authority` in `CodebaseProvider.materialize()` defaults to
`True` (`config.get("requires_authority", True)`), matching this session's
established fix for the 8 other real-side-effect providers
(`terraform_docker_apply.py`, `terraform_plan.py`, etc.) -- this provider
is being built fresh, so it is built with the correct default from day
one rather than needing a later retrofit. `materialization_requires_authority`
stays `False` per the same established convention: materialize() itself is
not authority-gated, only DO-capability actuation inside the materialized
environment is.

`restore()` implements exactly one real dimension -- "filesystem" (the
worktree's tracked-file state at a real commit SHA), via a real `git reset
--hard <sha>` when that commit is still reachable in the worktree's own
history, falling back to a real `clone_at_ref()` rebuild when the
checkpoint recorded a clone-at-ref source and the commit is no longer
locally reachable (e.g. the worktree was corrupted or replaced). Every
other restore dimension a real environment might need -- dependencies,
environment variables, containers, services -- is explicitly UNSUPPORTED:
requesting one via `restore(checkpoint, dimensions=(...))` raises
`NotImplementedError` naming exactly which dimension is missing, rather
than silently no-opping and pretending the environment was restored.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

_MAX_CAPTURED_OUTPUT = 20000
_DEFAULT_GIT_TIMEOUT_SECONDS = 30.0
_DEFAULT_TEST_TIMEOUT_SECONDS = 120.0
_DEFAULT_BUILD_TIMEOUT_SECONDS = 120.0
_DEFAULT_CLONE_TIMEOUT_SECONDS = 90.0


def _bounded_path(root: Path, relative: str) -> Path:
    """Resolve `relative` under `root`, refusing any path traversal outside
    the worktree. Mirrors `gymact.local_providers._bounded_path`."""
    if not relative or Path(relative).is_absolute():
        raise ValueError("AMBIGUOUS_SUBJECT_REFUSED")
    candidate = (root / relative).resolve()
    # `root` must be resolved to the same canonical form as `candidate`:
    # on macOS, `tempfile.mkdtemp()` returns `/var/...` while `.resolve()`
    # produces `/private/var/...` (`/var` is a symlink), so comparing the
    # raw root against a resolved candidate raised a spurious
    # AMBIGUOUS_SUBJECT_REFUSED for every seed file (PROVIDER_ERROR on
    # materialize, GYMACT-6 hermetic-suite repair).
    try:
        candidate.relative_to(Path(root).resolve())
    except ValueError as exc:
        raise ValueError("AMBIGUOUS_SUBJECT_REFUSED") from exc
    return candidate


# --------------------------------------------------------------------------
# Manifest-type detection (generalization #1): a real, filesystem-only
# check for which ecosystem's manifest is present at a repo root.
# --------------------------------------------------------------------------


class ProjectKind(StrEnum):
    """Detected build/test ecosystem for a codebase worktree."""

    RUST = "rust"
    ELIXIR = "elixir"
    NODE = "node"
    PYTHON = "python"
    GO = "go"
    MIXED = "mixed"
    UNKNOWN = "unknown"


# Only ecosystems with a real dispatchable toolchain below are keyed here;
# MIXED/UNKNOWN are derived, never looked up directly.
_MANIFEST_MARKERS: dict[ProjectKind, tuple[str, ...]] = {
    ProjectKind.RUST: ("Cargo.toml",),
    ProjectKind.ELIXIR: ("mix.exs",),
    ProjectKind.NODE: ("package.json",),
    ProjectKind.GO: ("go.mod",),
    ProjectKind.PYTHON: ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"),
}


def detect_project_kind(root: Path) -> ProjectKind:
    """Real, non-recursive manifest detection at `root`.

    Checks only the repo root for `Cargo.toml` (rust), `mix.exs` (elixir),
    `package.json` (node), `go.mod` (go), and any of `pyproject.toml` /
    `requirements.txt` / `setup.py` / `setup.cfg` (python) -- the same
    place each ecosystem's own tooling looks for its manifest. Returns:

      - the single matching `ProjectKind` when exactly one ecosystem's
        marker(s) are present,
      - `ProjectKind.MIXED` when more than one ecosystem's markers are
        present side by side (e.g. a python wrapper around a rust
        extension), and
      - `ProjectKind.UNKNOWN` when none are found.
    """
    root = Path(root)
    present: set[ProjectKind] = set()
    for kind, markers in _MANIFEST_MARKERS.items():
        if any((root / marker).is_file() for marker in markers):
            present.add(kind)
    if not present:
        return ProjectKind.UNKNOWN
    if len(present) > 1:
        return ProjectKind.MIXED
    return next(iter(present))


# --------------------------------------------------------------------------
# Per-kind build/test dispatch (generalization #2).
# --------------------------------------------------------------------------


def _python_files(worktree: Path) -> list[str]:
    return sorted(
        str(p.relative_to(worktree))
        for p in worktree.rglob("*.py")
        if ".git" not in p.parts
    )


def _node_package_manager(worktree: Path) -> str:
    if (worktree / "pnpm-lock.yaml").is_file() and shutil.which("pnpm"):
        return "pnpm"
    return "npm"


def _node_has_build_script(worktree: Path) -> bool:
    package_json = worktree / "package.json"
    if not package_json.is_file():
        return False
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    scripts = data.get("scripts")
    return isinstance(scripts, dict) and "build" in scripts


def _refuse_ambiguous_kind(kind: ProjectKind) -> None:
    if kind is ProjectKind.MIXED:
        raise ValueError(
            "PROJECT_KIND_MIXED_AMBIGUOUS_REFUSED: more than one manifest "
            "(Cargo.toml/mix.exs/package.json/go.mod/pyproject.toml) is "
            "present at the worktree root -- pass an explicit "
            "{'kind': '<rust|elixir|node|python|go>'} payload to disambiguate"
        )
    if kind is ProjectKind.UNKNOWN:
        raise ValueError(
            "PROJECT_KIND_UNKNOWN_REFUSED: no recognized manifest "
            "(Cargo.toml/mix.exs/package.json/go.mod/pyproject.toml) found "
            "at the worktree root"
        )


def _build_commands_for(kind: ProjectKind, worktree: Path) -> list[list[str]]:
    _refuse_ambiguous_kind(kind)
    if kind is ProjectKind.PYTHON:
        return [[sys.executable, "-m", "py_compile", *_python_files(worktree)]]
    if kind is ProjectKind.RUST:
        return [["cargo", "build"]]
    if kind is ProjectKind.ELIXIR:
        return [["mix", "deps.get"], ["mix", "compile"]]
    if kind is ProjectKind.NODE:
        pm = _node_package_manager(worktree)
        commands = [[pm, "install"]]
        if _node_has_build_script(worktree):
            commands.append([pm, "run", "build"])
        return commands
    if kind is ProjectKind.GO:
        return [["go", "build", "./..."]]
    raise AssertionError(f"unhandled project kind: {kind!r}")  # pragma: no cover


def _test_commands_for(kind: ProjectKind, worktree: Path) -> list[list[str]]:
    _refuse_ambiguous_kind(kind)
    if kind is ProjectKind.PYTHON:
        return [[sys.executable, "-m", "pytest", "-q"]]
    if kind is ProjectKind.RUST:
        return [["cargo", "test"]]
    if kind is ProjectKind.ELIXIR:
        return [["mix", "deps.get"], ["mix", "test"]]
    if kind is ProjectKind.NODE:
        pm = _node_package_manager(worktree)
        return [[pm, "install"], [pm, "test"]]
    if kind is ProjectKind.GO:
        return [["go", "test", "./..."]]
    raise AssertionError(f"unhandled project kind: {kind!r}")  # pragma: no cover


def _resolve_project_kind(payload: dict[str, Any], worktree: Path) -> ProjectKind:
    override = payload.get("kind")
    if override is not None:
        try:
            return ProjectKind(str(override))
        except ValueError as exc:
            raise ValueError(f"unknown project kind override: {override!r}") from exc
    detected = detect_project_kind(worktree)
    if detected is ProjectKind.UNKNOWN and _python_files(worktree):
        # No recognized manifest, but real .py files are present. Before
        # per-kind dispatch existed, this gym always ran pytest/py_compile
        # unconditionally -- a manifest-less python fixture (the common
        # case for ad hoc seed_files-only test repos) must keep working
        # exactly as before rather than being refused as UNKNOWN.
        return ProjectKind.PYTHON
    return detected


def _run_sequence(commands: list[list[str]], *, cwd: Path, timeout: float) -> dict[str, Any]:
    """Run each command in `commands` in order against a real subprocess,
    stopping at the first nonzero exit code. Every step's real
    returncode/stdout/stderr is preserved in `steps`; the top-level
    returncode/stdout/stderr mirror the last step actually run, matching
    the single-command shape this module used before dispatch existed."""
    steps: list[dict[str, Any]] = []
    for command in commands:
        process = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        steps.append(
            {
                "command": command,
                "returncode": process.returncode,
                "stdout": process.stdout[-_MAX_CAPTURED_OUTPUT:],
                "stderr": process.stderr[-_MAX_CAPTURED_OUTPUT:],
            }
        )
        if process.returncode != 0:
            break
    last = steps[-1]
    return {
        "returncode": last["returncode"],
        "stdout": last["stdout"],
        "stderr": last["stderr"],
        "steps": steps,
    }


# --------------------------------------------------------------------------
# Clone-at-ref materialize primitive (generalization #3).
# --------------------------------------------------------------------------


def _is_local_git_repo(source: Path) -> bool:
    return source.is_dir() and (source / ".git").exists()


def _configure_local_git_identity(
    worktree: Path, *, timeout: float = _DEFAULT_GIT_TIMEOUT_SECONDS
) -> None:
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
            timeout=timeout,
            check=False,
        )


def clone_at_ref(
    source: str,
    sha: str,
    *,
    destination: Path | None = None,
    strategy: str = "auto",
    timeout: float = _DEFAULT_CLONE_TIMEOUT_SECONDS,
    force: bool = False,
) -> dict[str, Any]:
    """Materialize a real, isolated destination directory at an EXACT
    commit SHA from `source` (a local repo path or a remote git URL).

    Two real strategies, chosen automatically unless `strategy` pins one:

      - `"worktree"`: a real `git -C <source> worktree add --detach
        <destination> <sha>` -- used when `source` is itself a local git
        repository on this machine. Cheap (objects are shared with
        `source` via git's linked-worktree mechanism) and never touches
        `source`'s tracked files (only its shared `.git` administrative
        metadata gains a worktree registration, pruned defensively before
        every add so a prior destination at the same path never blocks a
        retry).
      - `"clone"`: a real `git clone --no-checkout <source> <destination>`
        followed by a real `git checkout --detach <sha>` -- used for a
        remote URL, or a local path that is not itself a git repository.
        Strictly read-only against `source`.

    Every step is a real subprocess call; any nonzero exit raises
    `RuntimeError` with the real captured stderr -- this never fabricates
    success. After checkout, the destination's real `HEAD` is verified
    (via `git rev-parse`) to resolve to exactly the requested `sha`
    (supporting short SHAs) before a receipt is returned, and real `git
    status --porcelain` determines the receipt's `clean` flag.

    Returns a receipt dict: `{source, requested_sha, resolved_sha,
    destination, strategy, clean}`.
    """
    if not isinstance(sha, str) or not sha.strip():
        raise ValueError("sha must be a non-empty string")
    if strategy not in ("auto", "clone", "worktree"):
        raise ValueError(f"unknown clone_at_ref strategy: {strategy!r}")

    source_path = Path(source).expanduser()
    is_local = _is_local_git_repo(source_path)
    if strategy == "auto":
        effective_strategy = "worktree" if is_local else "clone"
    else:
        effective_strategy = strategy
        if effective_strategy == "worktree" and not is_local:
            raise ValueError(
                f"strategy='worktree' requires a local git repository source; {source!r} is not one"
            )

    dest = Path(destination) if destination is not None else Path(
        tempfile.mkdtemp(prefix="gymact-codebase-clone-")
    )
    if dest.exists():
        if any(dest.iterdir()) and not force:
            raise FileExistsError(f"destination already exists and is non-empty: {dest}")
        shutil.rmtree(dest, ignore_errors=True)

    if effective_strategy == "worktree":
        # Defensive: if a prior clone_at_ref registered a worktree at this
        # exact path and it was later removed by plain directory deletion
        # (e.g. teardown()/restore()'s rmtree above) rather than a proper
        # `git worktree remove`, the source repo's administrative metadata
        # can still remember it. `prune` clears any such stale
        # registration before we ask git to create a fresh one there.
        subprocess.run(
            ["git", "-C", str(source_path), "worktree", "prune"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        result = subprocess.run(
            ["git", "-C", str(source_path), "worktree", "add", "--detach", str(dest), sha],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git worktree add --detach {dest} {sha} (source={source_path}) failed "
                f"(rc={result.returncode}): {result.stderr}"
            )
    else:
        source_for_clone = str(source_path) if source_path.exists() else str(source)
        clone_result = subprocess.run(
            ["git", "clone", "--no-checkout", source_for_clone, str(dest)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if clone_result.returncode != 0:
            raise RuntimeError(
                f"git clone {source_for_clone} {dest} failed "
                f"(rc={clone_result.returncode}): {clone_result.stderr}"
            )
        checkout_result = subprocess.run(
            ["git", "checkout", "--detach", sha],
            cwd=dest,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if checkout_result.returncode != 0:
            raise RuntimeError(
                f"git checkout --detach {sha} in {dest} failed "
                f"(rc={checkout_result.returncode}): {checkout_result.stderr}"
            )

    resolved = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if resolved.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD in {dest} failed: {resolved.stderr}")
    resolved_sha = resolved.stdout.strip()

    requested_resolved = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", sha],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if requested_resolved.returncode != 0 or requested_resolved.stdout.strip() != resolved_sha:
        raise RuntimeError(
            f"clone_at_ref post-check failed: HEAD={resolved_sha!r} does not match "
            f"requested sha {sha!r} (resolved to {requested_resolved.stdout.strip()!r}) in {dest}"
        )

    status = subprocess.run(
        ["git", "-C", str(dest), "status", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    clean = status.returncode == 0 and status.stdout.strip() == ""

    return {
        "source": str(source),
        "requested_sha": sha,
        "resolved_sha": resolved_sha,
        "destination": str(dest),
        "strategy": effective_strategy,
        "clean": clean,
    }


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


_RESTORE_FILESYSTEM_DIMENSION = "filesystem"
# Named explicitly so restore() can raise NotImplementedError naming the
# exact missing dimension instead of silently no-opping. None of these are
# implemented by this minimal gym today.
_RESTORE_UNSUPPORTED_DIMENSIONS = ("dependencies", "env_vars", "containers", "services")


class CodebaseEnvironment:
    """Real, isolated local git worktree wrapped as a GymAct environment."""

    def __init__(
        self,
        *,
        worktree: Path,
        requires_authority: bool = True,
        source: str | None = None,
        source_sha: str | None = None,
    ) -> None:
        self.environment_id = f"urn:gymact:codebase:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._worktree = worktree.resolve()
        self._closed = False
        # Provenance recorded only when this environment was materialized
        # via clone_at_ref (config.clone_source/clone_sha) -- None for the
        # default from-scratch `git init` path. Used by restore() as a
        # rebuild fallback when the worktree's own git history no longer
        # reaches the checkpointed commit.
        self._source = source
        self._source_sha = source_sha

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def _run_git(
        self, args: list[str], *, timeout: float = _DEFAULT_GIT_TIMEOUT_SECONDS
    ) -> subprocess.CompletedProcess[str]:
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
                after = {
                    "path": relative,
                    "exists": True,
                    "content": target.read_text(encoding="utf-8"),
                }
        elif binding == "inspect_manifest":
            manifest_name = None
            content = None
            for candidate in (
                "pyproject.toml",
                "requirements.txt",
                "Cargo.toml",
                "mix.exs",
                "package.json",
                "go.mod",
            ):
                candidate_path = self._worktree / candidate
                if candidate_path.is_file():
                    manifest_name = candidate
                    content = candidate_path.read_text(encoding="utf-8")
                    break
            after = {
                "manifest": manifest_name,
                "content": content,
                "project_kind": detect_project_kind(self._worktree).value,
            }
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
            kind = _resolve_project_kind(payload, self._worktree)
            commands = _test_commands_for(kind, self._worktree)
            result = _run_sequence(
                commands, cwd=self._worktree, timeout=_DEFAULT_TEST_TIMEOUT_SECONDS
            )
            after = {
                "project_kind": kind.value,
                "returncode": result["returncode"],
                "passed": result["returncode"] == 0,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "steps": result["steps"],
            }
        elif binding == "run_build":
            kind = _resolve_project_kind(payload, self._worktree)
            commands = _build_commands_for(kind, self._worktree)
            result = _run_sequence(
                commands, cwd=self._worktree, timeout=_DEFAULT_BUILD_TIMEOUT_SECONDS
            )
            files_compiled = _python_files(self._worktree) if kind is ProjectKind.PYTHON else None
            after = {
                "project_kind": kind.value,
                "returncode": result["returncode"],
                "built": result["returncode"] == 0,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "steps": result["steps"],
                "files_compiled": files_compiled,
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
        observed = await self.observe()
        head_result = self._run_git(["rev-parse", "HEAD"])
        observed["head_sha"] = head_result.stdout.strip() if head_result.returncode == 0 else None
        observed["source"] = self._source
        observed["source_sha"] = self._source_sha
        return observed

    async def restore(
        self,
        checkpoint: dict[str, Any],
        *,
        dimensions: tuple[str, ...] = (_RESTORE_FILESYSTEM_DIMENSION,),
    ) -> dict[str, Any]:
        """Real, PARTIAL restore(). See the module docstring for the exact
        contract. Only the `"filesystem"` dimension (tracked-file state at
        a real commit SHA) is implemented; every other dimension a real
        codebase environment might need to restore -- `"dependencies"`
        (installed packages / vendored deps / lockfile state), `"env_vars"`
        (process environment at checkpoint time), `"containers"`, and
        `"services"` (any long-running local/service process state) --
        raises `NotImplementedError` naming exactly which one is missing.
        The default call shape (`restore(checkpoint)`, one positional arg,
        matching `gymact.providers.Environment`'s Protocol) always resolves
        to the filesystem dimension only, so every existing caller keeps
        working unchanged.
        """
        self._ensure_open()
        requested = tuple(dimensions)
        unsupported = [d for d in requested if d in _RESTORE_UNSUPPORTED_DIMENSIONS]
        if unsupported:
            raise NotImplementedError(
                "CodebaseEnvironment.restore() does not implement dimension(s) "
                f"{unsupported!r} -- only {_RESTORE_FILESYSTEM_DIMENSION!r} (tracked "
                "file state via git) is implemented. Dependencies, environment "
                "variables, containers, and services are explicitly UNSUPPORTED, "
                "never silently skipped."
            )
        unrecognized = [d for d in requested if d != _RESTORE_FILESYSTEM_DIMENSION]
        if unrecognized:
            raise ValueError(f"unknown restore dimension(s): {unrecognized!r}")

        head_sha = checkpoint.get("head_sha")
        if not isinstance(head_sha, str) or not head_sha:
            raise TypeError(
                "checkpoint['head_sha'] must be a non-empty commit SHA string "
                "(produce it via this environment's own checkpoint())"
            )

        probe = self._run_git(["cat-file", "-e", f"{head_sha}^{{commit}}"])
        if probe.returncode == 0:
            reset_result = self._run_git(["reset", "--hard", head_sha])
            if reset_result.returncode != 0:
                raise RuntimeError(f"git reset --hard {head_sha} failed: {reset_result.stderr}")
            clean_result = self._run_git(["clean", "-fdx"])
            return {
                "dimension": _RESTORE_FILESYSTEM_DIMENSION,
                "method": "git_reset_hard",
                "head_sha": head_sha,
                "reset_returncode": reset_result.returncode,
                "clean_returncode": clean_result.returncode,
            }

        source = checkpoint.get("source")
        source_sha = checkpoint.get("source_sha")
        if not source or not source_sha:
            raise RuntimeError(
                f"restore target commit {head_sha!r} is not reachable in this "
                "worktree's own git history, and the checkpoint records no "
                "clone-at-ref source to rebuild from -- filesystem state cannot "
                "be restored"
            )
        receipt = clone_at_ref(str(source), str(source_sha), destination=self._worktree, force=True)
        return {
            "dimension": _RESTORE_FILESYSTEM_DIMENSION,
            "method": "clone_at_ref_rebuild",
            "receipt": receipt,
        }

    async def teardown(self) -> None:
        if self._closed:
            return
        shutil.rmtree(self._worktree, ignore_errors=True)
        self._closed = True


class CodebaseProvider:
    """Materializes a `CodebaseEnvironment` over a fresh, isolated real
    temporary git repository -- or, when `config.clone_source` +
    `config.clone_sha` are given, over a real clone-at-ref checkout of a
    real repo. Never the caller's own working repo."""

    name = "codebase"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> CodebaseEnvironment:
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

        clone_source = config.get("clone_source")
        clone_sha = config.get("clone_sha")
        if (clone_source is None) != (clone_sha is None):
            raise TypeError("config.clone_source and config.clone_sha must be provided together")

        source_identity: str | None = None
        source_sha: str | None = None

        if clone_source is not None:
            receipt = clone_at_ref(str(clone_source), str(clone_sha))
            worktree = Path(receipt["destination"])
            source_identity = str(clone_source)
            source_sha = receipt["resolved_sha"]
        else:
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

        _configure_local_git_identity(worktree)

        if seed_files:
            for relative, content in seed_files.items():
                target = _bounded_path(worktree, str(relative))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(content), encoding="utf-8")

        return CodebaseEnvironment(
            worktree=worktree,
            requires_authority=requires_authority,
            source=source_identity,
            source_sha=source_sha,
        )


__all__ = [
    "CODEBASE_CAPABILITIES",
    "CodebaseEnvironment",
    "CodebaseProvider",
    "ProjectKind",
    "clone_at_ref",
    "detect_project_kind",
]
