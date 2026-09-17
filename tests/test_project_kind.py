"""Real, filesystem-only tests for `gymact.gyms.codebase.detect_project_kind`.

Chicago-style: every fixture is a real directory on disk (`tmp_path`), real
manifest files actually written to it, and `detect_project_kind()` invoked
directly against the real `Path` -- no mocking of `Path.is_file` or the
filesystem, matching this repo's testing discipline.
"""

from __future__ import annotations

from pathlib import Path

from gymact.gyms.codebase import ProjectKind, detect_project_kind


def _write(root: Path, relative: str, content: str = "") -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def test_detects_rust_from_cargo_toml(tmp_path: Path) -> None:
    _write(tmp_path, "Cargo.toml", '[package]\nname = "fixture"\nversion = "0.1.0"\n')
    _write(tmp_path, "src/main.rs", "fn main() {}\n")
    assert detect_project_kind(tmp_path) is ProjectKind.RUST


def test_detects_elixir_from_mix_exs(tmp_path: Path) -> None:
    _write(tmp_path, "mix.exs", "defmodule Fixture.MixProject do\nend\n")
    assert detect_project_kind(tmp_path) is ProjectKind.ELIXIR


def test_detects_node_from_package_json(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", '{"name": "fixture", "version": "1.0.0"}\n')
    assert detect_project_kind(tmp_path) is ProjectKind.NODE


def test_detects_go_from_go_mod(tmp_path: Path) -> None:
    _write(tmp_path, "go.mod", "module fixture\n\ngo 1.21\n")
    assert detect_project_kind(tmp_path) is ProjectKind.GO


def test_detects_python_from_pyproject_toml(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", '[project]\nname = "fixture"\n')
    assert detect_project_kind(tmp_path) is ProjectKind.PYTHON


def test_detects_python_from_requirements_txt_alone(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "requests==2.31.0\n")
    assert detect_project_kind(tmp_path) is ProjectKind.PYTHON


def test_detects_python_from_setup_py_alone(tmp_path: Path) -> None:
    _write(tmp_path, "setup.py", "from setuptools import setup\nsetup(name='fixture')\n")
    assert detect_project_kind(tmp_path) is ProjectKind.PYTHON


def test_empty_directory_is_unknown(tmp_path: Path) -> None:
    assert detect_project_kind(tmp_path) is ProjectKind.UNKNOWN


def test_directory_with_unrelated_files_is_unknown(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# fixture\n")
    _write(tmp_path, "notes.txt", "just some notes\n")
    assert detect_project_kind(tmp_path) is ProjectKind.UNKNOWN


def test_two_manifests_side_by_side_is_mixed(tmp_path: Path) -> None:
    # e.g. a python wrapper around a real rust extension -- both markers
    # for real, at the same root.
    _write(tmp_path, "Cargo.toml", '[package]\nname = "ext"\nversion = "0.1.0"\n')
    _write(tmp_path, "pyproject.toml", '[project]\nname = "wrapper"\n')
    assert detect_project_kind(tmp_path) is ProjectKind.MIXED


def test_three_manifests_side_by_side_is_still_mixed(tmp_path: Path) -> None:
    _write(tmp_path, "Cargo.toml", '[package]\nname = "ext"\nversion = "0.1.0"\n')
    _write(tmp_path, "package.json", '{"name": "web"}\n')
    _write(tmp_path, "go.mod", "module fixture\n")
    assert detect_project_kind(tmp_path) is ProjectKind.MIXED


def test_manifest_file_as_a_directory_does_not_count(tmp_path: Path) -> None:
    # A directory literally named "Cargo.toml" is not a manifest file --
    # detect_project_kind must check is_file(), not mere path existence.
    (tmp_path / "Cargo.toml").mkdir()
    assert detect_project_kind(tmp_path) is ProjectKind.UNKNOWN


def test_all_project_kind_enum_values_match_task_vocabulary() -> None:
    assert {member.value for member in ProjectKind} == {
        "rust",
        "elixir",
        "node",
        "python",
        "go",
        "mixed",
        "unknown",
    }
