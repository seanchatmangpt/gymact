"""Chicago-style: a real GymAct episode driving `DevPortfolioProvider` over
real local git repos and (network permitting) a real public GitHub repo --
not simulated, no mocking of `git`/`gh` subprocess calls.

`DevPortfolioProvider.materialization_requires_authority = False` and every
capability is `Consequence.READ`, so unlike `test_codebase.py` these tests
don't need an `AllowListAuthorityResolver` -- there is no `DO` actuation to
gate. Per `kernel.py`'s own `READ_CAPABILITY_IS_NOT_ACTUATION` refusal,
`gym.act()` never routes to a `READ` capability -- these tests exercise the
real kernel READ port, `gym.observe(episode_id)`, instead (confirmed against
`kernel.py:529` before writing this file, not assumed from `test_codebase.py`,
which reads `env.observe()` directly rather than through the kernel). The
GitHub half is skipped, by name, when `gh` is unavailable or unauthenticated
-- never faked with a mocked response.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from gymact import GymAct, MaterializationIntent
from gymact.gyms.dev_portfolio import DEV_PORTFOLIO_CAPABILITIES, DevPortfolioProvider


def _gh_available() -> bool:
    if shutil.which("gh") is None:
        return False
    result = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True, timeout=15, check=False
    )
    return result.returncode == 0


async def _gym() -> GymAct:
    gym = GymAct()
    gym.register_provider(DevPortfolioProvider())
    return gym


def _make_dirty_repo(tmp_path):
    repo = tmp_path / "dirty-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
    (repo / "a.txt").write_text("v1")
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, capture_output=True, check=True)
    (repo / "a.txt").write_text("v2 -- dirty")  # real uncommitted change
    return repo


def _make_clean_repo(tmp_path):
    repo = tmp_path / "clean-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
    (repo / "b.txt").write_text("v1")
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, capture_output=True, check=True)
    return repo


async def test_snapshot_local_state_reports_real_dirty_and_clean_repos(tmp_path) -> None:
    dirty = _make_dirty_repo(tmp_path)
    clean = _make_clean_repo(tmp_path)

    gym = await _gym()
    m = await gym.materialize(
        MaterializationIntent(
            provider="dev_portfolio",
            config={"local_repos": {"dirty": str(dirty), "clean": str(clean)}},
        )
    )
    assert m.accepted is True
    episode_id = m.episode.episode_id
    try:
        env = gym._episodes[episode_id].environment
        assert env.capabilities() == DEV_PORTFOLIO_CAPABILITIES

        observation = await gym.observe(episode_id)
        observed = observation.state

        assert observed["local_repos"]["dirty"]["exists"] is True
        assert observed["local_repos"]["dirty"]["dirty_files"] == 1
        assert observed["local_repos"]["clean"]["dirty_files"] == 0
        assert observed["local_repos"]["clean"]["branch"] in ("main", "master")
    finally:
        await gym.teardown(episode_id)


async def test_snapshot_local_state_reports_missing_repo_honestly(tmp_path) -> None:
    missing = tmp_path / "does-not-exist"

    gym = await _gym()
    m = await gym.materialize(
        MaterializationIntent(
            provider="dev_portfolio",
            config={"local_repos": {"missing": str(missing)}},
        )
    )
    episode_id = m.episode.episode_id
    try:
        observation = await gym.observe(episode_id)
        assert observation.state["local_repos"]["missing"]["exists"] is False
    finally:
        await gym.teardown(episode_id)


async def test_verify_fails_on_a_wrong_expectation_real_negative_case(tmp_path) -> None:
    """Real negative-case proof: asserting a known-dirty repo has 0 dirty
    files must genuinely fail `verify()`, not silently pass."""
    dirty = _make_dirty_repo(tmp_path)

    gym = await _gym()
    m = await gym.materialize(
        MaterializationIntent(
            provider="dev_portfolio",
            config={"local_repos": {"dirty": str(dirty)}},
        )
    )
    episode_id = m.episode.episode_id
    try:
        wrong = await gym.verify(episode_id, {"local_repos": {"dirty": {"dirty_files": 0}}})
        assert wrong.passed is False

        right = await gym.verify(episode_id, {"local_repos": {"dirty": {"dirty_files": 1}}})
        assert right.passed is True
    finally:
        await gym.teardown(episode_id)


async def test_teardown_is_idempotent() -> None:
    gym = await _gym()
    m = await gym.materialize(MaterializationIntent(provider="dev_portfolio", config={}))
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment
    await gym.teardown(episode_id)
    # A second, real teardown call on the same underlying environment must
    # not raise -- matches AzureGoatPrivescEnvironment's documented contract.
    await env.teardown()


@pytest.mark.skipif(not _gh_available(), reason="gh CLI not installed/authenticated in this environment")
async def test_snapshot_github_state_against_a_real_small_public_repo() -> None:
    # octocat/Hello-World: GitHub's own minimal, stable demo repo -- cheap,
    # public, and long-lived, so this test doesn't depend on any of the
    # user's own private repos.
    gym = await _gym()
    m = await gym.materialize(
        MaterializationIntent(
            provider="dev_portfolio",
            config={"github_repos": ["octocat/Hello-World"]},
        )
    )
    episode_id = m.episode.episode_id
    try:
        observation = await gym.observe(episode_id)
        repo_state = observation.state["github_repos"]["octocat/Hello-World"]
        assert "open_pr_count" in repo_state
        assert isinstance(repo_state["open_pr_count"], int)
        assert isinstance(repo_state["branch_count"], int)
        assert repo_state["branch_count"] >= 1  # at least a default branch
    finally:
        await gym.teardown(episode_id)
