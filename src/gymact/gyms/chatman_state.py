"""Real, live-loaded snapshot of the actual operator's current portfolio
state -- local git repositories on this machine and this GitHub account's
own repositories -- as a queryable, cost-aware fact source.

Why this module exists
-----------------------
Every gym in this repo so far models an external domain (cloud topology,
Kubernetes resource kinds, sregym scenarios). This one models the operator
running gymact: what am I actually building right now, and what has it
actually cost. There is no simulated or synthetic data here -- every fact
comes from a real, live call against this machine's own filesystem
(`.git` directories under `$HOME`) or this session's own already-
authenticated `gh` CLI session (`gh auth status`, confirmed live).

Scope, bounded and disclosed on purpose
----------------------------------------
This machine has on the order of 100+ local git checkouts and the
`seanchatmangpt` GitHub account has an unbounded, growing repo count --
too many to real-`git log` every one of on every call. "Current state" is
best represented by *recency*, not full historical coverage, so both
`discover_local_repos` and `discover_github_repos` cap their real result at
`limit` (default 25), sorted by real recency, and always report the real
total found alongside the real total returned -- so a cap is a disclosed,
checkable fact, never a silent truncation.

`estimated_effort_cost`'s hour figure is a **named, disclosed heuristic**,
not a measurement of actual wall-clock time worked: 0.25h per real commit,
plus 1h per 500 real lines changed (insertions + deletions from `git log
--shortstat`), both summed over the real commits in the window. This
constant lives here, in exactly one place -- change it here, not at any
call site.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from gymact.models import CostDimension

__all__ = [
    "LocalRepoState",
    "GithubRepoState",
    "discover_local_repos",
    "discover_github_repos",
    "estimated_effort_cost",
]

#: The named heuristic constants `estimated_effort_cost` uses -- see module
#: docstring. Change here only.
_HOURS_PER_COMMIT = 0.25
_HOURS_PER_500_LINES_CHANGED = 1.0
_COST_SOURCE = "commit-and-diff-size-heuristic-v1"


@dataclass(frozen=True, slots=True)
class LocalRepoState:
    """One real local git checkout under `$HOME`, found by a real,
    depth-bounded filesystem scan."""

    name: str
    path: str
    head_mtime: float
    #: "<ahead>\\t<behind>" from a real `git rev-list --left-right --count
    #: HEAD...@{u}`, or `None` if this repo has no configured upstream --
    #: never fabricated when genuinely absent.
    ahead_behind_origin: str | None


@dataclass(frozen=True, slots=True)
class GithubRepoState:
    """One real repository from `gh repo list <owner> --json ...`."""

    name: str
    pushed_at: str
    primary_language: str | None
    is_private: bool


def discover_local_repos(
    *, root: Path | None = None, max_depth: int = 2, limit: int = 25
) -> tuple[LocalRepoState, ...]:
    """Real, depth-bounded scan for `.git` directories under `root`
    (default `$HOME`), returning the `limit` most recently active real
    repos by `.git/HEAD`'s real mtime, descending. Never scans deeper than
    `max_depth` path components below `root` -- a full-depth `$HOME` walk
    is not bounded and would be far too slow to run at every
    materialize().
    """
    base = root if root is not None else Path.home()
    base = base.resolve()
    found: list[LocalRepoState] = []
    seen_paths: set[Path] = set()
    for depth in range(1, max_depth + 1):
        pattern = "/".join(["*"] * depth) + "/.git"
        for git_dir in base.glob(pattern):
            if not git_dir.is_dir() or git_dir.parent in seen_paths:
                continue
            seen_paths.add(git_dir.parent)
            repo_path = git_dir.parent
            head = git_dir / "HEAD"
            try:
                mtime = head.stat().st_mtime
            except OSError:
                continue
            ahead_behind = _real_ahead_behind(repo_path)
            found.append(
                LocalRepoState(
                    name=repo_path.name,
                    path=str(repo_path),
                    head_mtime=mtime,
                    ahead_behind_origin=ahead_behind,
                )
            )
    found.sort(key=lambda r: r.head_mtime, reverse=True)
    return tuple(found[:limit])


def count_local_repos(*, root: Path | None = None, max_depth: int = 2) -> int:
    """Real total count of `.git` directories found at any depth from 1
    through `max_depth` below `root`, unbounded by `limit` -- so callers
    can report the real cap-vs-total honestly."""
    base = (root if root is not None else Path.home()).resolve()
    seen_paths: set[Path] = set()
    for depth in range(1, max_depth + 1):
        pattern = "/".join(["*"] * depth) + "/.git"
        for git_dir in base.glob(pattern):
            if git_dir.is_dir():
                seen_paths.add(git_dir.parent)
    return len(seen_paths)


def _real_ahead_behind(repo_path: Path) -> str | None:
    try:
        upstream = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "@{u}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if upstream.returncode != 0:
            return None
        counts = subprocess.run(
            ["git", "-C", str(repo_path), "rev-list", "--left-right", "--count", "HEAD...@{u}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if counts.returncode != 0:
            return None
        return counts.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def discover_github_repos(*, owner: str = "seanchatmangpt", limit: int = 25) -> tuple[GithubRepoState, ...]:
    """Real `gh repo list <owner> --json name,pushedAt,primaryLanguage,
    isPrivate --limit <limit>` call, parsed into typed rows, already
    ordered by real `pushedAt` descending (the CLI's own default ordering,
    verified this session)."""
    import json

    result = subprocess.run(
        [
            "gh",
            "repo",
            "list",
            owner,
            "--json",
            "name,pushedAt,primaryLanguage,isPrivate",
            "--limit",
            str(limit),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    rows = json.loads(result.stdout)
    return tuple(
        GithubRepoState(
            name=row["name"],
            pushed_at=row["pushedAt"],
            primary_language=(row.get("primaryLanguage") or {}).get("name"),
            is_private=row["isPrivate"],
        )
        for row in rows
    )


def count_github_repos(*, owner: str = "seanchatmangpt") -> int:
    """Real total repo count for `owner`, via `gh api users/<owner> --jq
    .public_repos` -- unbounded by any `--limit`, so a caller can report
    the real cap-vs-total honestly. Counts public repos only (matches what
    `discover_github_repos` can see without additional private-repo
    listing scope)."""
    result = subprocess.run(
        ["gh", "api", f"users/{owner}", "--jq", ".public_repos"],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    return int(result.stdout.strip())


def estimated_effort_cost(repo_path: Path, *, since: str = "7 days ago") -> CostDimension:
    """Real `git log --since=<since> --shortstat` over `repo_path`, folded
    into one `CostDimension` (`unit="engineering_hour"`) via the named
    heuristic documented at module level. Zero real commits in the window
    yields `quantity=0.0` honestly -- never a fabricated non-zero floor.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_path), "log", f"--since={since}", "--shortstat", "--pretty=format:COMMIT"],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    commit_count = result.stdout.count("COMMIT")
    lines_changed = 0
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if "changed" not in stripped:
            continue
        for token in stripped.split(","):
            token = token.strip()
            if "insertion" in token or "deletion" in token:
                lines_changed += int(token.split()[0])
    hours = commit_count * _HOURS_PER_COMMIT + (lines_changed / 500.0) * _HOURS_PER_500_LINES_CHANGED
    return CostDimension(
        unit="engineering_hour",
        quantity=round(hours, 2),
        kind="declared_estimate",
        source=_COST_SOURCE,
    )
