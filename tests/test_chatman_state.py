"""Chicago-style: real filesystem scans and real `gh`/`git` subprocess calls
against this actual machine and this actual, already-authenticated `gh`
session -- no mocked subprocess output, no synthetic repo fixtures. Skips by
name (not silently) if `gh`/`git` are genuinely absent from PATH.

No `unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere
in this file.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gymact.gyms.chatman_state import (
    count_github_repos,
    count_local_repos,
    discover_github_repos,
    discover_local_repos,
    estimated_effort_cost,
)

pytestmark = pytest.mark.skipif(
    shutil.which("gh") is None or shutil.which("git") is None,
    reason="real gh/git CLI required on PATH",
)


def test_discover_local_repos_finds_this_real_repo() -> None:
    repos = discover_local_repos(root=Path.home(), limit=200)
    names = {r.name for r in repos}
    assert "gymact" in names, "this checkout itself must be discoverable"


def test_discover_local_repos_respects_real_limit_and_recency_order() -> None:
    repos = discover_local_repos(root=Path.home(), limit=5)
    assert len(repos) <= 5
    mtimes = [r.head_mtime for r in repos]
    assert mtimes == sorted(mtimes, reverse=True), "must be sorted most-recent-first"


def test_count_local_repos_is_at_least_the_capped_result_size() -> None:
    total = count_local_repos(root=Path.home())
    capped = discover_local_repos(root=Path.home(), limit=5)
    assert total >= len(capped)


def test_discover_github_repos_returns_real_recent_repos() -> None:
    repos = discover_github_repos(owner="seanchatmangpt", limit=5)
    assert len(repos) <= 5
    assert len(repos) > 0
    for repo in repos:
        assert repo.name
        assert repo.pushed_at


def test_count_github_repos_is_a_real_positive_int() -> None:
    total = count_github_repos(owner="seanchatmangpt")
    assert isinstance(total, int)
    assert total > 0


def test_estimated_effort_cost_on_this_real_repo_is_a_real_nonnegative_cost() -> None:
    cost = estimated_effort_cost(Path.home() / "gymact", since="30 days ago")
    assert cost.unit == "engineering_hour"
    assert cost.kind == "declared_estimate"
    assert cost.source == "commit-and-diff-size-heuristic-v1"
    assert cost.quantity >= 0.0


def test_estimated_effort_cost_is_zero_for_a_window_with_no_real_commits() -> None:
    # `--since` selects commits AFTER the given date -- a far-future date is
    # guaranteed to have zero real commits in this checkout's history.
    cost = estimated_effort_cost(Path.home() / "gymact", since="2099-01-01")
    assert cost.quantity == 0.0
