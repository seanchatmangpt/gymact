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
`Environment` contract instead of a one-off script. This is a new pattern for
gymact: nothing else in `gymact/src/gymact/gyms/*.py` calls the GitHub API or
`gh` CLI today (confirmed by grep before writing this file).
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


def _run(args: list[str], *, cwd: Path | None = None, timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _snapshot_one_local_repo(path: Path) -> dict[str, Any]:
    if not path.is_dir():
        return {"path": str(path), "exists": False}
    status = _run(["git", "status", "--porcelain"], cwd=path)
    branch = _run(["git", "branch", "--show-current"], cwd=path)
    log = _run(["git", "log", "-1", "--format=%h %cI %s"], cwd=path)
    dirty_lines = [line for line in status.stdout.splitlines() if line.strip()]
    return {
        "path": str(path),
        "exists": True,
        "branch": branch.stdout.strip(),
        "dirty_files": len(dirty_lines),
        "last_commit": log.stdout.strip(),
        "git_status_returncode": status.returncode,
    }


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

    open_prs = json.loads(pr_result.stdout) if pr_result.returncode == 0 and pr_result.stdout.strip() else []
    open_issues_ok = issue_result.returncode == 0
    open_issues = json.loads(issue_result.stdout) if open_issues_ok and issue_result.stdout.strip() else []
    all_branches = [b for b in branches_result.stdout.splitlines() if b.strip()] if branches_result.returncode == 0 else []
    pr_heads = {pr["headRefName"] for pr in open_prs}
    stale_branches = [b for b in all_branches if b not in pr_heads and b not in ("main", "master")]

    return {
        "repo": owner_slash_name,
        "open_pr_count": len(open_prs),
        "open_prs": open_prs,
        "issues_disabled": not open_issues_ok and "disabled" in issue_result.stderr.lower(),
        "open_issue_count": len(open_issues) if open_issues_ok else None,
        "open_issues": open_issues,
        "branch_count": len(all_branches),
        "stale_branch_count": len(stale_branches),
        "stale_branches": stale_branches,
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
