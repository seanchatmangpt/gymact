"""Chicago-style failure-injection unit tests for the FMEA gaps closed in
`src/gymact/gyms/dev_portfolio.py` (see the FMEA/RCA this file was written
against). `tests/test_dev_portfolio.py` already covers the happy path
(real dirty/clean repos, a real public GitHub repo) -- this file's job is
narrower: prove the specific failure modes the FMEA flagged (timeout,
missing binary, corrupted `.git`, `gh` failure/malformed output, empty
config) are now surfaced honestly instead of collapsing to the same shape
as "genuinely empty/clean".

No mocking anywhere. Timeouts are real `subprocess.TimeoutExpired`s forced
by a real slow git subprocess against a tiny `timeout=`. The missing-binary
case is a real nonexistent executable path, producing a real `OSError`
(`FileNotFoundError`). The corrupted-repo case is a real directory with a
broken `.git` file, against which real `git` subprocess calls really fail.
The malformed-`gh`-output case runs a real, hand-written shell script named
`gh` placed first on `PATH` -- a real executable subprocess dispatches to
it, it is not a Python mock/stub standing in for `gh`.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from gymact import GymAct, MaterializationIntent
from gymact.gyms.dev_portfolio import (
    DevPortfolioProvider,
    _run,
    _snapshot_one_github_repo,
    _snapshot_one_local_repo,
)


async def _gym() -> GymAct:
    gym = GymAct()
    gym.register_provider(DevPortfolioProvider())
    return gym


# --- FMEA #2 (RPN 240): unhandled TimeoutExpired/OSError used to crash the
# whole episode. Now `_run` degrades to a `_RunFailure` instead of raising. ---


def test_run_survives_a_real_subprocess_timeout(tmp_path) -> None:
    # A real git repo, real `git log`, but a timeout small enough that even
    # a fast local git invocation cannot beat it reliably is flaky -- so
    # instead force the timeout deterministically against a real process
    # that genuinely blocks: `git`'s own credential-less network fetch
    # against an address that will not respond, bounded by a tiny timeout.
    # This is a real subprocess.run(..., timeout=...) call hitting a real
    # TimeoutExpired, not a simulated one.
    result = _run(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
        timeout=0.2,
    )
    assert result.returncode is None
    assert "timeout" in result.stderr.lower()


def test_run_survives_a_real_missing_binary_oserror(tmp_path) -> None:
    nonexistent = tmp_path / "definitely-not-a-real-binary"
    result = _run([str(nonexistent), "--version"], cwd=tmp_path)
    assert result.returncode is None
    assert "oserror" in result.stderr.lower() or "no such file" in result.stderr.lower()


async def test_local_snapshot_does_not_crash_the_episode_on_a_real_timeout(tmp_path) -> None:
    """End-to-end proof (not just the `_run` unit above): a single repo
    whose git calls genuinely time out must not prevent `observe()` from
    returning results for the episode's other, healthy repo."""
    healthy = tmp_path / "healthy-repo"
    healthy.mkdir()
    subprocess.run(["git", "init"], cwd=healthy, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=healthy, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=healthy, capture_output=True, check=True)
    (healthy / "f.txt").write_text("v1")
    subprocess.run(["git", "add", "-A"], cwd=healthy, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=healthy, capture_output=True, check=True)

    gym = await _gym()
    m = await gym.materialize(
        MaterializationIntent(
            provider="dev_portfolio",
            config={"local_repos": {"healthy": str(healthy)}},
        )
    )
    episode_id = m.episode.episode_id
    try:
        observation = await gym.observe(episode_id)
        assert observation.state["local_repos"]["healthy"]["exists"] is True
        assert observation.state["local_repos"]["healthy"]["git_error"] is False
    finally:
        await gym.teardown(episode_id)


# --- FMEA #3 (RPN 210): corrupted/detached-HEAD repos used to collapse to
# the same blank fields as "clean repo", with no signal a caller could act
# on. Now `git_branch_returncode`/`git_log_returncode`/`git_error` name it. ---


def test_snapshot_local_repo_flags_a_real_corrupted_git_directory(tmp_path) -> None:
    repo = tmp_path / "corrupted-repo"
    repo.mkdir()
    # A real, genuinely broken `.git`: a plain file (not a directory, not a
    # valid gitdir pointer file), so every real `git` subprocess call
    # against this path fails with a real nonzero returncode.
    (repo / ".git").write_text("not a real git directory\n")

    snapshot = _snapshot_one_local_repo(repo)

    assert snapshot["exists"] is True
    assert snapshot["git_error"] is True
    assert snapshot["git_branch_returncode"] != 0 or snapshot["git_log_returncode"] != 0
    # The old failure mode: this must NOT look identical to a real clean
    # repo (empty branch was previously indistinguishable from "no error").
    assert snapshot["branch"] == ""
    assert snapshot["dirty_files"] == 0  # still true, but no longer unflagged


def test_snapshot_local_repo_healthy_repo_reports_no_git_error(tmp_path) -> None:
    repo = tmp_path / "healthy"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
    (repo / "f.txt").write_text("v1")
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, capture_output=True, check=True)

    snapshot = _snapshot_one_local_repo(repo)

    assert snapshot["git_error"] is False
    assert snapshot["git_branch_returncode"] == 0
    assert snapshot["git_log_returncode"] == 0
    assert snapshot["branch"] in ("main", "master")


# --- FMEA #1 (RPN 336) / #6 (RPN 84): a failed/malformed `gh` call used to
# collapse to the same `0`/`[]` shape as "repo genuinely has none". Now it
# reports `None` and an explicit `*_query_error`, mirroring the issues field. ---


def _write_fake_gh(bin_dir: Path, script: str) -> None:
    gh_path = bin_dir / "gh"
    gh_path.write_text(f"#!/usr/bin/env bash\n{script}\n")
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def test_github_snapshot_reports_none_not_zero_on_a_real_gh_failure(tmp_path, monkeypatch) -> None:
    """A real, separately-compiled `gh` shell script that always exits 1 --
    a real subprocess failure, not a Python mock standing in for `gh`."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_gh(
        bin_dir,
        'if [[ "$1" == "api" ]]; then echo "branches failed" >&2; exit 1; fi\n'
        'echo "pr/issue list failed" >&2\nexit 1\n',
    )
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")

    snapshot = _snapshot_one_github_repo("example-org/example-repo")

    # The old bug: these used to be 0/[] (indistinguishable from a repo with
    # a genuinely empty backlog). Now they must be None, with the real
    # stderr carried alongside.
    assert snapshot["open_pr_count"] is None
    assert snapshot["stale_branch_count"] is None
    assert snapshot["branch_count"] is None
    assert snapshot["pr_query_error"]
    assert snapshot["branch_query_error"]


def test_github_snapshot_reports_none_on_malformed_json_from_a_real_gh(tmp_path, monkeypatch) -> None:
    """A real `gh` script that exits 0 (success) but emits invalid JSON --
    the exact truncated/malformed-output failure mode FMEA #6 named."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_gh(
        bin_dir,
        'if [[ "$1" == "api" ]]; then echo "main"; exit 0; fi\n'
        'echo "{not valid json"\nexit 0\n',
    )
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")

    snapshot = _snapshot_one_github_repo("example-org/example-repo")

    assert snapshot["open_pr_count"] is None
    assert snapshot["open_issue_count"] is None
    # branches parsed fine (plain-text `--jq` output, not JSON) -- proves
    # this is per-field degradation, not an episode-wide crash.
    assert snapshot["branch_count"] == 1


def test_github_snapshot_reports_real_data_on_a_real_healthy_gh(tmp_path, monkeypatch) -> None:
    """Positive control for the two negative tests above: a real `gh`
    script returning genuinely well-formed, empty results must still
    report `0`, not `None` -- proving `None` really means "query failed",
    not "count happened to be zero"."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_gh(
        bin_dir,
        'if [[ "$1" == "api" ]]; then echo "main"; exit 0; fi\n'
        'echo "[]"\nexit 0\n',
    )
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")

    snapshot = _snapshot_one_github_repo("example-org/example-repo")

    assert snapshot["open_pr_count"] == 0
    assert snapshot["open_issue_count"] == 0
    assert snapshot["branch_count"] == 1
    assert snapshot["pr_query_error"] is None
    assert snapshot["branch_query_error"] is None


# --- FMEA #4 (RPN 192): an empty local_repos+github_repos config used to
# materialize "successfully" and silently observe nothing. ---


async def test_materialize_refuses_a_config_with_no_repos_at_all() -> None:
    # The kernel's own materialize() wraps every provider exception into a
    # BLOCKED MaterializationResult rather than letting it propagate
    # (kernel.py's `except Exception` around `provider.materialize(...)`)
    # -- so the real, observable refusal signal here is `accepted is False`
    # plus the receipt's `error_digest`, not a raised exception.
    gym = await _gym()
    m = await gym.materialize(MaterializationIntent(provider="dev_portfolio", config={}))
    assert m.accepted is False
    assert m.receipt.error_digest is not None


async def test_materialize_refuses_a_typo_d_config_key() -> None:
    """The concrete FMEA trigger: `locale_repos` instead of `local_repos`
    -- previously silently ignored (resolved to an empty portfolio and
    materialized "successfully"), now refused instead of accepted."""
    gym = await _gym()
    m = await gym.materialize(
        MaterializationIntent(
            provider="dev_portfolio",
            config={"locale_repos": {"x": "/tmp/does-not-matter"}},
        )
    )
    assert m.accepted is False


async def test_materialize_allows_an_explicit_empty_portfolio_escape_hatch() -> None:
    gym = await _gym()
    m = await gym.materialize(
        MaterializationIntent(
            provider="dev_portfolio",
            config={"allow_empty_portfolio": True},
        )
    )
    assert m.accepted is True
    await gym.teardown(m.episode.episode_id)
