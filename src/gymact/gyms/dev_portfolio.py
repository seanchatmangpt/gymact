"""Real GymAct `Environment`/`EnvironmentProvider` observing the user's own
real dev-portfolio state -- local git worktrees plus GitHub PR/issue/branch
backlog across their real repos. Not simulated: every fact returned by
`observe()` comes from a real `git`/`gh` subprocess call made at actuation
time.

This domain is READ-only by design (`Consequence.READ` on every capability,
never `DO`): it snapshots state, it never merges a PR, deletes a branch, or
mutates a local worktree. `DevPortfolioEnvironment(requires_authority=False)`
is an intentional, documented deviation from `codebase.py`'s `True` default
-- that default exists to gate *actuation of a DO capability*; this domain
has none, so there is nothing to gate.

Local repos are read via a bounded, explicit `local_repos` config list (never
an open-ended filesystem walk -- mirrors `codebase.py`'s `_bounded_path`
containment discipline, just applied to "which repos may be inspected" rather
than "which paths inside one worktree"). GitHub repos are read the same way
this session's own ad-hoc cross-repo audit did it -- real `gh pr list`/`gh
issue list`/`gh api .../branches` subprocess calls -- now behind the stable
`Environment` contract instead of a one-off script. This is not the first
gymact gym to call the GitHub API or `gh` CLI: `chatman_state.py` (backing
`chatman_state_gym.py`) already does, via its own `discover_github_repos`/
`count_github_repos` real `gh` subprocess calls. The two gyms differ in
shape, not in whether they touch GitHub: `dev_portfolio.py` is a bounded,
explicit-allowlist PR/issue/branch backlog view over named repos supplied by
config; `chatman_state.py` is an open-ended, recency-sorted discovery scan
over an owner's repos, with no caller-supplied allowlist.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

_DEFAULT_TIMEOUT_SECONDS = 30.0
_GH_TIMEOUT_SECONDS = 60.0


def _bounded_repo_path(allowed: dict[str, Path], name: str) -> Path:
    """Refuse any local-repo lookup outside the materialized allowlist --
    mirrors `codebase.py`'s `_bounded_path` refusal discipline, applied to
    "which named repo" rather than "which path inside one worktree"."""
    if name not in allowed:
        raise ValueError(f"AMBIGUOUS_SUBJECT_REFUSED: {name!r} not in configured local_repos")
    return allowed[name]


class _RunFailure:
    """Sentinel standing in for a `CompletedProcess` when the subprocess
    itself never completed (timeout, missing binary, OS-level failure) --
    distinct from `check=False`'s "ran, but exited nonzero" case. Carries
    `returncode=None` (never a real exit code) plus a human-readable
    `stderr` so callers can tell "failed to run" from "ran and said no"."""

    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, stderr: str) -> None:
        self.returncode: int | None = None
        self.stdout = ""
        self.stderr = stderr


def _run(
    args: list[str], *, cwd: Path | None = None, timeout: float = _DEFAULT_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str] | _RunFailure:
    """Real subprocess call, hardened against the two failure modes that
    used to crash the whole episode (FMEA RPN 240): a hung process
    (`subprocess.TimeoutExpired`) and a process that never started at all
    (`OSError`, e.g. binary vanished between `shutil.which` and exec).
    Both are reported as a `_RunFailure` (never raised) so one bad repo
    degrades that repo's snapshot instead of aborting every other repo's."""
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _RunFailure(f"timeout after {timeout}s running {' '.join(args)!r}")
    except OSError as exc:
        return _RunFailure(f"OSError running {' '.join(args)!r}: {exc}")


def _snapshot_one_local_repo(path: Path) -> dict[str, Any]:
    if not path.is_dir():
        return {"path": str(path), "exists": False}
    status = _run(["git", "status", "--porcelain"], cwd=path)
    branch = _run(["git", "branch", "--show-current"], cwd=path)
    log = _run(["git", "log", "-1", "--format=%h %cI %s"], cwd=path)
    dirty_lines = [line for line in status.stdout.splitlines() if line.strip()]
    # FMEA RPN 210: a detached HEAD / corrupted `.git` / any subprocess
    # failure on branch/log used to collapse into the same blank fields as
    # "genuinely clean repo" -- now every one of the three calls' returncode
    # is captured, and `git_error` names the failure explicitly rather than
    # leaving it to be inferred from empty strings.
    git_error = any(r.returncode != 0 for r in (status, branch, log))
    return {
        "path": str(path),
        "exists": True,
        "branch": branch.stdout.strip(),
        "dirty_files": len(dirty_lines),
        "last_commit": log.stdout.strip(),
        "git_status_returncode": status.returncode,
        "git_branch_returncode": branch.returncode,
        "git_log_returncode": log.returncode,
        "git_error": git_error,
    }


def _json_or_none(result: subprocess.CompletedProcess[str] | _RunFailure) -> Any | None:
    """Parse `gh`'s stdout as JSON, or `None` on any failure -- a failed/
    empty/malformed subprocess result must never be indistinguishable from
    a real, successfully-parsed empty JSON array (FMEA RPN 336, RPN 84)."""
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _snapshot_one_github_repo(owner_slash_name: str) -> dict[str, Any]:
    gh_binary = shutil.which("gh")
    if gh_binary is None:
        return {"repo": owner_slash_name, "error": "gh CLI not on PATH"}

    pr_result = _run(
        [
            "gh", "pr", "list", "--repo", owner_slash_name, "--state", "open",
            "--json", "number,title,headRefName,isDraft,mergeable", "--limit", "50",
        ],
        timeout=_GH_TIMEOUT_SECONDS,
    )
    issue_result = _run(
        [
            "gh", "issue", "list", "--repo", owner_slash_name, "--state", "open",
            "--json", "number,title", "--limit", "50",
        ],
        timeout=_GH_TIMEOUT_SECONDS,
    )
    branches_result = _run(
        ["gh", "api", f"repos/{owner_slash_name}/branches", "--paginate", "--jq", ".[].name"],
        timeout=_GH_TIMEOUT_SECONDS,
    )

    # FMEA RPN 336: a failed `pr_result`/`branches_result` call used to
    # collapse to the same `0`/`[]` shape as "repo genuinely has none" --
    # now both mirror the `open_issues_ok`/`None` pattern the issues branch
    # already used, rather than silently reporting a false "zero backlog".
    open_prs = _json_or_none(pr_result)
    open_prs_ok = open_prs is not None
    open_issues_ok = issue_result.returncode == 0
    open_issues = _json_or_none(issue_result) if open_issues_ok else None
    branches_ok = branches_result.returncode == 0
    all_branches = (
        [b for b in branches_result.stdout.splitlines() if b.strip()] if branches_ok else None
    )
    pr_heads = {pr["headRefName"] for pr in (open_prs or [])}
    stale_branches = (
        [b for b in all_branches if b not in pr_heads and b not in ("main", "master")]
        if all_branches is not None
        else None
    )

    return {
        "repo": owner_slash_name,
        "open_pr_count": len(open_prs) if open_prs_ok else None,
        "open_prs": open_prs if open_prs_ok else [],
        "pr_query_error": None if open_prs_ok else pr_result.stderr,
        "issues_disabled": not open_issues_ok and "disabled" in issue_result.stderr.lower(),
        "open_issue_count": len(open_issues) if open_issues_ok and open_issues is not None else None,
        "open_issues": open_issues if open_issues else [],
        "branch_count": len(all_branches) if branches_ok else None,
        "stale_branch_count": len(stale_branches) if stale_branches is not None else None,
        "stale_branches": stale_branches if stale_branches is not None else [],
        "branch_query_error": None if branches_ok else branches_result.stderr,
    }


DEV_PORTFOLIO_CAPABILITIES = (
    Capability(
        iri="urn:gymact:dev-portfolio:capability:snapshot_local_state",
        title="snapshot_local_state",
        consequence=Consequence.READ,
        binding="snapshot_local_state",
    ),
    Capability(
        iri="urn:gymact:dev-portfolio:capability:snapshot_github_state",
        title="snapshot_github_state",
        consequence=Consequence.READ,
        binding="snapshot_github_state",
    ),
    Capability(
        iri="urn:gymact:dev-portfolio:capability:snapshot_full_portfolio",
        title="snapshot_full_portfolio",
        consequence=Consequence.READ,
        binding="snapshot_full_portfolio",
    ),
)


class DevPortfolioEnvironment:
    """Real, read-only snapshot of the user's local repos + GitHub backlog.

    No `DO` capability exists in this domain -- `requires_authority` defaults
    to `False` here (unlike `codebase.py`'s `True` default), documented as an
    intentional deviation: that gate exists for actuation of a `DO`
    capability, and this domain has none.
    """

    def __init__(
        self,
        *,
        local_repos: dict[str, Path],
        github_repos: tuple[str, ...],
        requires_authority: bool = False,
    ) -> None:
        self.environment_id = f"urn:gymact:dev-portfolio:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._local_repos = local_repos
        self._github_repos = github_repos
        self._last_snapshot: dict[str, Any] | None = None
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return DEV_PORTFOLIO_CAPABILITIES

    def _local_snapshot(self) -> dict[str, dict[str, Any]]:
        return {name: _snapshot_one_local_repo(path) for name, path in self._local_repos.items()}

    def _github_snapshot(self) -> dict[str, dict[str, Any]]:
        return {repo: _snapshot_one_github_repo(repo) for repo in self._github_repos}

    async def observe(self) -> dict[str, Any]:
        """The real kernel READ port (`GymAct.observe(episode_id)` calls this
        directly, with no capability selection -- READ capabilities exist
        for RDF/documentation parity with `DO` domains, but per
        `kernel.py`'s own `READ_CAPABILITY_IS_NOT_ACTUATION` refusal, `act()`
        never routes to them; `observe()` is the one real, always-fresh read
        path, matching `codebase.py`'s `observe()`, which likewise redoes its
        real `git log`/`git status` calls on every invocation rather than
        caching)."""
        self._ensure_open()
        snapshot = {
            "local_repos": self._local_snapshot(),
            "github_repos": self._github_snapshot(),
        }
        self._last_snapshot = snapshot
        return snapshot

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        """Direct-call convenience matching each declared capability's scope
        (local-only / github-only / full). Not reachable via `GymAct.act()`
        for a READ capability (the kernel refuses before dispatch here) --
        this exists so a caller holding the `Environment` directly, or a
        future `DO`-domain sibling, can still request a narrower real read
        than the kernel's `observe()` port gives."""
        del payload
        self._ensure_open()
        before = self._last_snapshot
        binding = capability.binding

        if binding == "snapshot_local_state":
            after = {"local_repos": self._local_snapshot()}
        elif binding == "snapshot_github_state":
            after = {"github_repos": self._github_snapshot()}
        elif binding == "snapshot_full_portfolio":
            after = await self.observe()
        else:
            raise ValueError(f"unsupported dev_portfolio binding: {binding}")

        self._last_snapshot = after
        return {"before": before, "after": after}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Real state-based check: re-runs `observe()` (fresh `git`/`gh`
        calls) rather than trusting a cached snapshot, matching
        `codebase.py`'s `verify()` -- and unlike this session's earlier
        AzureGoat self-report bug, this domain has no separate "actuated"
        state to diverge from what a fresh read shows, since every read here
        is idempotent by construction."""
        self._ensure_open()
        observed = await self.observe()

        def _check(node: Any, exp: Any) -> bool:
            if isinstance(exp, dict):
                if not isinstance(node, dict):
                    return False
                return all(key in node and _check(node[key], value) for key, value in exp.items())
            return node == exp

        passed = _check(observed, expected)
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return await self.observe()

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        """Intentionally causally inert for every protocol method that
        matters (FMEA #5): `verify()`/`observe()` always re-run real
        `git`/`gh` calls rather than consulting `self._last_snapshot`, by
        design, because every read in this domain is idempotent -- there is
        no external state for a restored checkpoint to roll back to (see
        `verify()`'s own docstring). This assignment exists only so a
        caller reading `._last_snapshot` directly after `restore()` sees
        the checkpoint value; it is not consulted by any Environment
        protocol method, and should not be read as implying that calling
        `restore()` changes what `observe()`/`verify()` report next."""
        self._ensure_open()
        self._last_snapshot = checkpoint or None

    async def teardown(self) -> None:
        # Real, idempotent no-op: this domain holds no external resource
        # (no subprocess handle, no temp dir, no network socket) between
        # actuate() calls -- every gh/git call is fire-and-forget. Safe to
        # call repeatedly, matching AzureGoatPrivescEnvironment.teardown().
        self._closed = True


class DevPortfolioProvider:
    """Materializes a `DevPortfolioEnvironment` over a bounded, explicit set
    of local repo paths and GitHub `org/repo` slugs. Never scans the
    filesystem or the user's GitHub account open-endedly -- both lists are
    config-supplied allowlists."""

    name = "dev_portfolio"
    materialization_requires_authority = False

    async def materialize(self, *, scenario: str | None, config: dict[str, Any]) -> DevPortfolioEnvironment:
        del scenario

        raw_local = config.get("local_repos")
        if raw_local is not None and not isinstance(raw_local, dict):
            raise TypeError("config.local_repos must be a dict[str, str] of {name: path}")
        local_repos: dict[str, Path] = {
            name: Path(str(path)).expanduser().resolve()
            for name, path in (raw_local or {}).items()
        }

        raw_github = config.get("github_repos")
        if raw_github is not None and not isinstance(raw_github, (list, tuple)):
            raise TypeError("config.github_repos must be a list[str] of 'owner/name' slugs")
        github_repos: tuple[str, ...] = tuple(str(r) for r in (raw_github or ()))

        requires_authority = config.get("requires_authority", False)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")

        # FMEA RPN 192: a typo'd config key (e.g. `locale_repos`) or an
        # omitted `local_repos`/`github_repos` used to silently resolve to
        # an empty portfolio that materializes, "succeeds", and produces a
        # 0-event OCEL log with no signal anything was wrong -- a
        # Decorative Completion per this repo's own coding-agent-mistakes
        # taxonomy. Refuse it explicitly instead. `allow_empty_portfolio`
        # is an explicit, named escape hatch for the one legitimate empty
        # case (`test_teardown_is_idempotent`-style teardown-only tests),
        # so refusal stays the default without making the empty case
        # unreachable for callers who genuinely want it.
        if not local_repos and not github_repos and not config.get("allow_empty_portfolio", False):
            raise ValueError(
                "dev_portfolio: config.local_repos and config.github_repos both "
                "resolved empty -- refusing to materialize a portfolio that "
                "would silently observe nothing. Check for a typo'd config key, "
                "or pass allow_empty_portfolio=True if this is intentional."
            )

        return DevPortfolioEnvironment(
            local_repos=local_repos,
            github_repos=github_repos,
            requires_authority=requires_authority,
        )


__all__ = [
    "DEV_PORTFOLIO_CAPABILITIES",
    "DevPortfolioEnvironment",
    "DevPortfolioProvider",
    "_bounded_repo_path",
]
