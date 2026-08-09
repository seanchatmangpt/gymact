from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gymact.gyms.ggen import GGEN_CAPABILITIES, GgenProvider
from gymact.models import Consequence
from gymact.registry import builtin_provider_names


def _fixture_pack(source: Path) -> None:
    source.mkdir()
    (source / "pack.toml").write_text('[pack]\nname="fixture"\nversion="0.1.0"\ndescription="real ggen gym smoke"\n')
    (source / "ontology.ttl").write_text("@prefix dct: <http://purl.org/dc/terms/> .\n")
    templates = source / "templates"
    templates.mkdir()
    (templates / "reference.md.tmpl").write_text('---\nto: "reference.md"\nforce: true\n---\n# protocol gym fixture\n')


def test_ggen_is_a_builtin_provider() -> None:
    assert "ggen" in builtin_provider_names()


def test_ggen_gym_classifies_only_sync_as_do() -> None:
    by_binding = {item.binding: item for item in GGEN_CAPABILITIES}
    assert by_binding["sync"].consequence is Consequence.DO
    assert by_binding["graph-validate"].consequence is Consequence.READ
    assert by_binding["doctor"].consequence is Consequence.READ
    assert by_binding["receipt-verify"].consequence is Consequence.READ


@pytest.mark.asyncio
async def test_ggen_gym_materializes_an_isolated_workspace(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _fixture_pack(source)
    environment = await GgenProvider().materialize(scenario=None, config={"source": str(source), "ggen_bin": shutil.which("ggen") or "ggen"})
    try:
        assert environment.workspace != source
        assert environment.workspace.is_dir()
        checkpoint = await environment.checkpoint()
        (environment.workspace / "ontology.ttl").write_text("mutated")
        await environment.restore(checkpoint)
        assert "http://purl.org/dc/terms/" in (environment.workspace / "ontology.ttl").read_text()
    finally:
        await environment.teardown()


@pytest.mark.asyncio
async def test_real_ggen_sync_when_binary_is_available(tmp_path: Path) -> None:
    ggen = shutil.which("ggen")
    if ggen is None:
        pytest.skip("REAL_GGEN_BINARY_MISSING")
    source = tmp_path / "source"
    _fixture_pack(source)
    environment = await GgenProvider().materialize(scenario=None, config={"source": str(source), "ggen_bin": ggen})
    try:
        sync = next(item for item in GGEN_CAPABILITIES if item.binding == "sync")
        result = await environment.actuate(sync, {})
        assert result["returncode"] == 0, result["stderr"]
        assert (environment.workspace / "reference.md").is_file()
        assert result["after"]["file_count"] >= 4
    finally:
        await environment.teardown()
