"""Chicago-style: real `ggen` subprocess actuation against a real, isolated
bundle workspace -- not simulated.

Per `gymact.standing.require_standing`, the real thing is the default: if no
real `ggen` binary is on PATH, this module FAILS unless the run explicitly
sets `GYMACT_ALLOW_DEGRADED_STANDINGS` to include "LOCAL_GYM:ggen" (or "*")
-- a skip here is something a run must opt into, never something it
silently gets. Matches `test_kubernetes_reconciliation.py`'s contract.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gymact.standing import require_standing


def _ggen_available() -> bool:
    return shutil.which("ggen") is not None


require_standing(
    "LOCAL_GYM:ggen",
    available=_ggen_available(),
    reason="no `ggen` binary found on PATH (install it, e.g. via "
    "`cargo install ggen`, or ensure ~/.cargo/bin is on PATH)",
)

from gymact.gyms.ggen import GGEN_CAPABILITIES, GgenProvider  # noqa: E402
from gymact.models import Consequence  # noqa: E402
from gymact.registry import builtin_provider_names  # noqa: E402


def _fixture_project(source: Path) -> None:
    source.mkdir()
    (source / "ggen.toml").write_text(
        '[project]\nname="fixture"\n\n'
        '[ontology]\nsource="ontology.ttl"\n\n'
        '[templates]\ndir="templates"\n'
    )
    (source / "ontology.ttl").write_text("@prefix dct: <http://purl.org/dc/terms/> .\n")
    templates = source / "templates"
    templates.mkdir()
    (templates / "reference.md.tmpl").write_text(
        '---\nto: "reference.md"\nforce: true\n---\n# protocol gym fixture\n'
    )


def test_ggen_is_a_builtin_provider() -> None:
    assert "ggen" in builtin_provider_names()


def test_ggen_gym_classifies_only_sync_as_do() -> None:
    by_binding = {item.binding: item for item in GGEN_CAPABILITIES}
    assert by_binding["sync"].consequence is Consequence.DO
    assert by_binding["graph-validate"].consequence is Consequence.READ
    assert by_binding["doctor"].consequence is Consequence.READ
    assert by_binding["receipt-verify"].consequence is Consequence.READ


@pytest.mark.asyncio
async def test_ggen_refuses_declared_dependency_outside_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    source = bundle / "source"
    _fixture_project(source)
    outside = tmp_path / "outside-pack"
    outside.mkdir()
    (outside / "pack.toml").write_text(
        '[pack]\nname="outside"\nversion="0.1.0"\ndescription="outside"\n'
    )
    (source / "ggen.toml").write_text(
        (source / "ggen.toml").read_text()
        + '\n[packs]\noutside = { path = "../../outside-pack" }\n'
    )
    with pytest.raises(ValueError, match="REFUSED:GGEN_DEPENDENCY_OUTSIDE_BUNDLE"):
        await GgenProvider().materialize(
            scenario=None,
            config={"source": str(source), "bundle_root": str(bundle)},
        )


@pytest.mark.asyncio
async def test_ggen_dependency_closure_copies_declared_pack_into_private_bundle(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    source = bundle / "source"
    _fixture_project(source)
    pack = bundle / "pack"
    pack.mkdir()
    (pack / "pack.toml").write_text(
        '[pack]\nname="fixture-pack"\nversion="0.1.0"\ndescription="fixture"\n'
    )
    (source / "ggen.toml").write_text(
        (source / "ggen.toml").read_text() + '\n[packs]\nfixture-pack = { path = "../pack" }\n'
    )

    environment = await GgenProvider().materialize(
        scenario=None,
        config={
            "source": str(source),
            "bundle_root": str(bundle),
            "ggen_bin": shutil.which("ggen") or "ggen",
        },
    )
    try:
        assert environment.workspace != source
        staged_pack = environment.workspace.parent / "pack"
        assert staged_pack.is_dir()
        assert staged_pack != pack
        assert (staged_pack / "pack.toml").read_text() == (pack / "pack.toml").read_text()
    finally:
        await environment.teardown()


@pytest.mark.asyncio
async def test_ggen_gym_materializes_an_isolated_workspace(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _fixture_project(source)
    environment = await GgenProvider().materialize(
        scenario=None,
        config={
            "source": str(source),
            "ggen_bin": shutil.which("ggen") or "ggen",
        },
    )
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
    source = tmp_path / "source"
    _fixture_project(source)
    environment = await GgenProvider().materialize(
        scenario=None,
        config={"source": str(source), "ggen_bin": ggen},
    )
    try:
        sync = next(item for item in GGEN_CAPABILITIES if item.binding == "sync")
        result = await environment.actuate(sync, {})
        assert result["returncode"] == 0, result["stderr"]
        assert (environment.workspace / "reference.md").is_file()
        assert result["after"]["file_count"] >= 4
    finally:
        await environment.teardown()


@pytest.mark.asyncio
async def test_real_ggen_graph_validate_when_binary_is_available(
    tmp_path: Path,
) -> None:
    ggen = shutil.which("ggen")
    source = tmp_path / "source"
    _fixture_project(source)
    environment = await GgenProvider().materialize(
        scenario=None,
        config={"source": str(source), "ggen_bin": ggen},
    )
    try:
        capability = next(item for item in GGEN_CAPABILITIES if item.binding == "graph-validate")
        # payload is ignored -- actuate()'s first statement is `del payload`.
        result = await environment.actuate(capability, {"ignored": "payload"})
        assert isinstance(result["returncode"], int)
        assert result["before"]["tree_digest"] == result["after"]["tree_digest"]
        assert result["after"]["receipt_present"] is False
    finally:
        await environment.teardown()


@pytest.mark.asyncio
async def test_real_ggen_doctor_when_binary_is_available(tmp_path: Path) -> None:
    ggen = shutil.which("ggen")
    source = tmp_path / "source"
    _fixture_project(source)
    environment = await GgenProvider().materialize(
        scenario=None,
        config={"source": str(source), "ggen_bin": ggen},
    )
    try:
        capability = next(item for item in GGEN_CAPABILITIES if item.binding == "doctor")
        result = await environment.actuate(capability, {})
        assert isinstance(result["returncode"], int)
        assert result["stdout"] or result["stderr"]
        assert result["before"]["tree_digest"] == result["after"]["tree_digest"]
    finally:
        await environment.teardown()


@pytest.mark.asyncio
async def test_real_ggen_receipt_verify_when_binary_is_available(
    tmp_path: Path,
) -> None:
    ggen = shutil.which("ggen")
    source = tmp_path / "source"
    _fixture_project(source)
    environment = await GgenProvider().materialize(
        scenario=None,
        config={"source": str(source), "ggen_bin": ggen},
    )
    try:
        capability = next(item for item in GGEN_CAPABILITIES if item.binding == "receipt-verify")
        # No receipt exists yet in a fresh bundle -- assert the real
        # subprocess ran and the plumbing returned real, unfabricated
        # observation state, not a specific success/failure outcome we
        # haven't personally observed.
        assert (await environment.observe())["receipt_present"] is False
        result = await environment.actuate(capability, {})
        assert isinstance(result["returncode"], int)
        assert result["before"]["receipt_present"] is False
        assert result["after"]["receipt_present"] is False
    finally:
        await environment.teardown()
