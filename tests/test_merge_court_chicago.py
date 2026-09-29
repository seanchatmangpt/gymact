"""Court for scripts/merge_court.py, run as a real subprocess against real temp trees.

No mocks: each case builds a real directory (and, for branch cases, a real git repo with
real commits) and asserts on the script's real exit code and JSON report.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "merge_court.py"

pytestmark = pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not on PATH")

CLEAN = "def add(a: int, b: int) -> int:\n    return a + b\n"
INIT_OK = 'from gymact.core import Thing\n\n__all__ = ["Thing"]\n'


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _court(root: Path, *extra: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.stdout.strip(), proc.stderr
    return proc.returncode, json.loads(proc.stdout)


def _git(root: Path, *args: str) -> str:
    env_args = ["-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]
    proc = subprocess.run(
        ["git", *env_args, *args], cwd=root, capture_output=True, text=True, check=True
    )
    return proc.stdout


def _commit_all(root: Path, msg: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-m", msg)


def _clean_tree(root: Path) -> None:
    _write(root, "src/gymact/__init__.py", INIT_OK)
    _write(root, "src/gymact/core.py", "class Thing:\n    pass\n")
    _write(root, "tests/test_ok.py", CLEAN)


def test_clean_tree_passes(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    code, report = _court(tmp_path)
    assert code == 0, report
    assert report["ok"] is True
    assert report["syntax_errors"] == []
    assert report["exports"] == {"checked": True, "missing_from_all": []}
    assert report["ruff"]["ok"] is True
    assert report["files_checked"] == 3


def test_indentation_error_is_reported(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path, "src/gymact/broken.py", "def f():\nreturn 1\n")
    code, report = _court(tmp_path)
    assert code != 0
    assert report["ok"] is False
    assert [e["file"] for e in report["syntax_errors"]] == ["src/gymact/broken.py"]
    assert report["syntax_errors"][0]["error"].startswith("IndentationError")


def test_import_missing_from_all_is_reported(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(
        tmp_path,
        "src/gymact/__init__.py",
        'from gymact.core import Thing, Other\n\n__all__ = ["Thing"]\n',
    )
    code, report = _court(tmp_path)
    assert code != 0
    assert report["exports"]["missing_from_all"] == ["Other"]


def test_ruff_format_violation_fails(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path, "tests/test_ugly.py", "x   =   {'a':1}\n")
    code, report = _court(tmp_path)
    assert code != 0
    assert report["ruff"]["ok"] is False
    assert report["ruff"]["format"]["returncode"] != 0


def test_ruff_lint_violation_fails_even_when_formatting_is_clean(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path, "tests/test_lint.py", "import os\n")  # F401, but format-clean
    code, report = _court(tmp_path)
    assert code != 0
    assert report["ruff"]["ok"] is False
    assert report["ruff"]["check"]["returncode"] != 0
    assert report["ruff"]["format"]["returncode"] == 0


def _branch_conflict_repo(root: Path, branch_text: str) -> None:
    _git(root, "init", "-b", "main")
    _write(root, "README.md", "base\n")
    _commit_all(root, "base")
    _git(root, "checkout", "-b", "feature")
    _write(root, "src/mod.py", branch_text)
    _commit_all(root, "feature adds mod")
    _git(root, "checkout", "main")
    _write(root, "src/mod.py", 'VALUE = {"a": 1, "b": 2}\n')
    _commit_all(root, "main adds mod")


def test_formatting_only_add_add_is_format_equivalent(tmp_path: Path) -> None:
    _branch_conflict_repo(tmp_path, 'VALUE = {"a": 1,\n  "b": 2}\n')
    code, report = _court(tmp_path, "--branch", "feature")
    assert report["add_add_conflicts"] == [{"file": "src/mod.py", "class": "format_equivalent"}]
    # Our own tree is ruff-clean, so a format-equivalent conflict must not fail the court.
    assert report["ruff"]["ok"] is True
    assert code == 0, report


def test_semantic_add_add_is_not_format_equivalent(tmp_path: Path) -> None:
    _branch_conflict_repo(tmp_path, "VALUE = {'a': 1, 'b': 3}\n")
    code, report = _court(tmp_path, "--branch", "feature")
    assert report["add_add_conflicts"] == [{"file": "src/mod.py", "class": "semantic"}]
    # Ruff is clean here, so the non-zero exit can only come from the semantic classification.
    assert report["ruff"]["ok"] is True
    assert code != 0
