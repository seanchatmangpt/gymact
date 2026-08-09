from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import Graph

from gymact.gyms.codebase import CODEBASE_CAPABILITIES, CodebaseProvider


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return completed.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "GymAct Test")
    _git(root, "config", "user.email", "gymact-test@example.invalid")
    (root / "pyproject.toml").write_text(
        '[project]\nname="demo"\nversion="0.1.0"\n', encoding="utf-8"
    )
    (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "initial")
    return root


def _cap(binding: str):
    return next(item for item in CODEBASE_CAPABILITIES if item.binding == binding)


@pytest.mark.asyncio
async def test_codebase_isolation_semantics_and_local_commit(tmp_path: Path) -> None:
    source = _repo(tmp_path)
    original_head = _git(source, "rev-parse", "HEAD")
    env = await CodebaseProvider().materialize(
        scenario=None,
        config={
            "root": str(source),
            "commands": {
                "test": [sys.executable, "-c", "import app; assert app.VALUE == 2"],
                "build": [sys.executable, "-m", "py_compile", "app.py"],
            },
        },
    )
    try:
        assert env.requires_authority is True
        observed = await env.observe()
        assert observed["head"] == original_head
        assert "pyproject.toml" in observed["manifests"]
        assert "spdx:Package" in observed["semantic_snapshot"]
        assert "spdx:Sbom" in observed["semantic_snapshot"]
        assert "schema:SoftwareSourceCode" in observed["semantic_snapshot"]
        assert f"swh:1:rev:{original_head}" in observed["semantic_snapshot"]
        assert "swh:1:cnt:" in observed["semantic_snapshot"]
        Graph().parse(data=observed["semantic_snapshot"], format="turtle")

        await env.actuate(
            _cap("apply_replacement"),
            {"path": "app.py", "before": "VALUE = 1", "after": "VALUE = 2"},
        )
        test_result = await env.actuate(_cap("run_test"), {})
        build_result = await env.actuate(_cap("run_build"), {})
        assert test_result["exit"] == 0
        assert build_result["exit"] == 0
        committed = await env.actuate(
            _cap("commit"), {"message": "fix: update value"}
        )
        assert committed["head"] != original_head

        assert (source / "app.py").read_text(encoding="utf-8") == "VALUE = 1\n"
        assert _git(source, "rev-parse", "HEAD") == original_head
    finally:
        await env.teardown()


@pytest.mark.asyncio
async def test_codebase_refuses_unadmitted_command_and_nonunique_patch(
    tmp_path: Path,
) -> None:
    source = _repo(tmp_path)
    env = await CodebaseProvider().materialize(scenario=None, config={"root": str(source)})
    try:
        with pytest.raises(ValueError, match="CODEBASE_COMMAND_NOT_ADMITTED"):
            await env.actuate(_cap("run_lint"), {})
        with pytest.raises(ValueError, match="REPLACEMENT_NOT_UNIQUE"):
            await env.actuate(
                _cap("apply_replacement"),
                {"path": "app.py", "before": "MISSING", "after": "X"},
            )
    finally:
        await env.teardown()


@pytest.mark.asyncio
async def test_codebase_checkpoint_restore_is_worktree_local(tmp_path: Path) -> None:
    source = _repo(tmp_path)
    env = await CodebaseProvider().materialize(scenario=None, config={"root": str(source)})
    try:
        checkpoint = await env.checkpoint()
        await env.actuate(
            _cap("write_text"), {"path": "new.txt", "text": "temporary\n"}
        )
        assert (env.root / "new.txt").is_file()
        await env.restore(checkpoint)
        assert not (env.root / "new.txt").exists()
        assert not (source / "new.txt").exists()
    finally:
        await env.teardown()
