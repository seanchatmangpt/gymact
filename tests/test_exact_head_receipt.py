from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "exact_head_receipt.py"


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _git(repo: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return process.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "subject"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "GymAct Court"], cwd=repo, check=True)
    (repo / "subject.txt").write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "subject.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "subject v1"], cwd=repo, check=True)
    return repo


def test_exact_head_receipt_is_deterministic_and_verifiable(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    first = _run(repo)
    second = _run(repo)

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert first.stdout == second.stdout

    receipt = json.loads(first.stdout)
    assert receipt["subject_sha"] == _git(repo, "rev-parse", "HEAD")
    assert receipt["tree_sha"] == _git(repo, "rev-parse", "HEAD^{tree}")
    assert receipt["clean_tracked_worktree"] is True

    path = tmp_path / "receipt.json"
    path.write_text(first.stdout, encoding="utf-8")
    verified = _run(repo, "--verify", str(path))
    assert verified.returncode == 0, verified.stdout + verified.stderr


def test_expected_sha_mismatch_refuses(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    refused = _run(repo, "--expected-sha", "0" * 40)

    assert refused.returncode == 1
    assert "REFUSED:EXACT_HEAD_MISMATCH" in refused.stdout


def test_tracked_worktree_edit_refuses_receipt(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "subject.txt").write_text("changed but uncommitted\n", encoding="utf-8")

    refused = _run(repo)

    assert refused.returncode == 1
    assert "REFUSED:TRACKED_WORKTREE_DIRTY" in refused.stdout


def test_new_commit_invalidates_old_receipt(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    initial = _run(repo)
    assert initial.returncode == 0

    path = tmp_path / "receipt.json"
    path.write_text(initial.stdout, encoding="utf-8")

    (repo / "subject.txt").write_text("v2\n", encoding="utf-8")
    subprocess.run(["git", "add", "subject.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "subject v2"], cwd=repo, check=True)

    refused = _run(repo, "--verify", str(path))
    assert refused.returncode == 1
    assert "REFUSED:EXACT_HEAD_RECEIPT_DRIFT:subject_sha" in refused.stdout
