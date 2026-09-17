"""Chicago-style: real `git` subprocess tests for
`gymact.gyms.codebase.clone_at_ref` -- no mocking of `subprocess.run` or of
git itself.

Three real sources are exercised:

  1. A tiny real git repository this test constructs via real `git init` +
     `git add` + `git commit` subprocess calls (mirroring
     `CodebaseProvider.materialize()`'s own from-scratch pattern) -- used
     for BOTH the "worktree" strategy (source is a local git repo) and the
     "clone" strategy (forced), so both real code paths in `clone_at_ref`
     are exercised against a real repo with a real, known two-commit
     history and two real, known SHAs.
  2. This very test suite's own real, already-existing repository checkout
     on this machine (`Path(__file__).resolve().parents[1]`) -- satisfying
     "test against one of this machine's own small repos" without ever
     touching the canonical `/Users/sac/gymact` checkout (a real `git
     clone` only *reads* its source; it writes nothing back into it), and
     without depending on a machine-specific absolute path that would make
     this test non-portable to another checkout of this same repo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gymact.gyms.codebase import clone_at_ref

_GIT_TIMEOUT = 30.0


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        check=True,
    )


def _make_real_source_repo(root: Path) -> tuple[str, str]:
    """Real `git init` + two real commits. Returns (first_sha, second_sha)."""
    _git(["init"], cwd=root)
    _git(["config", "user.email", "clone-at-ref-test@example.invalid"], cwd=root)
    _git(["config", "user.name", "clone-at-ref test"], cwd=root)
    (root / "README.md").write_text("first\n", encoding="utf-8")
    _git(["add", "-A"], cwd=root)
    _git(["commit", "-m", "first commit"], cwd=root)
    first_sha = _git(["rev-parse", "HEAD"], cwd=root).stdout.strip()

    (root / "README.md").write_text("second\n", encoding="utf-8")
    (root / "extra.txt").write_text("extra\n", encoding="utf-8")
    _git(["add", "-A"], cwd=root)
    _git(["commit", "-m", "second commit"], cwd=root)
    second_sha = _git(["rev-parse", "HEAD"], cwd=root).stdout.strip()

    return first_sha, second_sha


def test_clone_at_ref_worktree_strategy_pins_exact_local_commit(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    first_sha, second_sha = _make_real_source_repo(source)

    receipt = clone_at_ref(str(source), first_sha)
    try:
        assert receipt["strategy"] == "worktree"
        assert receipt["resolved_sha"] == first_sha
        assert receipt["resolved_sha"] != second_sha
        assert receipt["clean"] is True
        dest = Path(receipt["destination"])
        assert dest.is_dir()
        assert (dest / "README.md").read_text(encoding="utf-8") == "first\n"
        assert not (dest / "extra.txt").exists()  # not yet created at first_sha
        # Real, independent confirmation directly against git -- not just
        # trusting the receipt's own self-report.
        real_head = _git(["rev-parse", "HEAD"], cwd=dest).stdout.strip()
        assert real_head == first_sha
    finally:
        _git(
            ["-C", str(source), "worktree", "remove", "--force", receipt["destination"]],
            cwd=source,
        )


def test_clone_at_ref_worktree_strategy_never_writes_to_sources_tracked_files(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _first_sha, second_sha = _make_real_source_repo(source)
    before_status = _git(["status", "--porcelain"], cwd=source).stdout

    receipt = clone_at_ref(str(source), second_sha)
    try:
        after_status = _git(["status", "--porcelain"], cwd=source).stdout
        assert before_status == after_status == ""
        # The source's own checked-out commit is untouched by materializing
        # a worktree at another (here: the same) commit.
        assert _git(["rev-parse", "HEAD"], cwd=source).stdout.strip() == second_sha
    finally:
        _git(
            ["-C", str(source), "worktree", "remove", "--force", receipt["destination"]],
            cwd=source,
        )


def test_clone_at_ref_clone_strategy_pins_exact_commit_and_is_read_only_on_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    first_sha, second_sha = _make_real_source_repo(source)
    before_status = _git(["status", "--porcelain"], cwd=source).stdout

    receipt = clone_at_ref(str(source), first_sha, strategy="clone")

    assert receipt["strategy"] == "clone"
    assert receipt["resolved_sha"] == first_sha
    assert receipt["clean"] is True
    dest = Path(receipt["destination"])
    assert dest.is_dir()
    assert (dest / "README.md").read_text(encoding="utf-8") == "first\n"
    assert not (dest / "extra.txt").exists()

    # A real `git clone` never writes into its source's tracked state.
    after_status = _git(["status", "--porcelain"], cwd=source).stdout
    assert before_status == after_status == ""
    assert _git(["rev-parse", "HEAD"], cwd=source).stdout.strip() == second_sha


def test_clone_at_ref_auto_strategy_picks_worktree_for_a_local_git_repo(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    first_sha, _second_sha = _make_real_source_repo(source)

    receipt = clone_at_ref(str(source), first_sha, strategy="auto")
    try:
        assert receipt["strategy"] == "worktree"
    finally:
        _git(
            ["-C", str(source), "worktree", "remove", "--force", receipt["destination"]],
            cwd=source,
        )


def test_clone_at_ref_refuses_worktree_strategy_for_a_non_git_source(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "plain_dir"
    not_a_repo.mkdir()
    with pytest.raises(ValueError, match="requires a local git repository"):
        clone_at_ref(str(not_a_repo), "deadbeef", strategy="worktree")


def test_clone_at_ref_raises_runtimeerror_with_real_stderr_for_an_unknown_sha(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _make_real_source_repo(source)

    with pytest.raises(RuntimeError) as exc_info:
        clone_at_ref(str(source), "0" * 40, strategy="clone")
    assert "0000000000000000000000000000000000000000" in str(exc_info.value)


def test_clone_at_ref_supports_a_short_sha(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    first_sha, _second_sha = _make_real_source_repo(source)
    short_sha = first_sha[:10]

    receipt = clone_at_ref(str(source), short_sha, strategy="clone")
    assert receipt["resolved_sha"] == first_sha
    assert receipt["requested_sha"] == short_sha


def test_clone_at_ref_force_overwrites_an_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _first_sha, second_sha = _make_real_source_repo(source)

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "stale.txt").write_text("stale contents\n", encoding="utf-8")

    receipt = clone_at_ref(str(source), second_sha, destination=dest, strategy="clone", force=True)
    assert receipt["resolved_sha"] == second_sha
    assert not (dest / "stale.txt").exists()
    assert (dest / "extra.txt").is_file()


def test_clone_at_ref_refuses_a_non_empty_destination_without_force(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    first_sha, _second_sha = _make_real_source_repo(source)

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "stale.txt").write_text("stale\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        clone_at_ref(str(source), first_sha, destination=dest, strategy="clone")


def test_clone_at_ref_against_this_machines_own_real_repository_checkout() -> None:
    """Real "one of this machine's own small repos" case: this very test
    file's own real, already-existing repo checkout on disk -- a real git
    clone (read-only against the source) pinned at that repo's own real,
    current HEAD SHA, resolved live via a real `git rev-parse HEAD`
    against it, never hardcoded."""
    repo_root = Path(__file__).resolve().parents[1]
    assert (repo_root / ".git").exists(), f"expected a real repo at {repo_root}"
    real_head_sha = _git(["rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
    assert len(real_head_sha) == 40
    # Captured before, not asserted empty: this checkout legitimately has
    # its own real in-progress edits (including this very test file) while
    # this test runs, so "unaffected by clone_at_ref" means "identical
    # before vs. after", not "clean".
    status_before = _git(["status", "--porcelain"], cwd=repo_root).stdout

    receipt = clone_at_ref(str(repo_root), real_head_sha, strategy="clone")
    assert receipt["resolved_sha"] == real_head_sha
    dest = Path(receipt["destination"])
    assert dest.is_dir()
    assert (dest / "pyproject.toml").is_file()
    # Read-only: the real repo's own status/HEAD are unaffected.
    assert _git(["status", "--porcelain"], cwd=repo_root).stdout == status_before
    assert _git(["rev-parse", "HEAD"], cwd=repo_root).stdout.strip() == real_head_sha
