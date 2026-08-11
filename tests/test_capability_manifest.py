"""Real, Chicago-style tests for scripts/capability_manifest.py.

No mocks: runs the real manifest-building function against the real
gymact.registry._BUILTINS dict and asserts on the real, resulting JSON-
serializable structure -- not on "was registry imported."

Closes a real follow-up named by ~/ggen/packs/domain-capability-pack's own
pack.toml (uncommitted WIP as of 2026-08-11): a real, generated source of
truth for gymact's capability surface, so a downstream allowlist (e.g.
autofde-lab's gymact_capabilities.toml) has something real to check against
instead of a hand-copied, silently-driftable subset.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from capability_manifest import build_manifest, main  # noqa: E402

from gymact.gyms.sregym import SREGYM_CAPABILITIES  # noqa: E402
from gymact.registry import _BUILTINS  # noqa: E402


def test_manifest_is_json_serializable_with_the_documented_shape() -> None:
    manifest = build_manifest()

    # Round-trips through real json.dumps/loads -- not merely "looks dict-like".
    rendered = json.dumps(manifest)
    reloaded = json.loads(rendered)

    assert reloaded["schema"] == "gymact-capability-manifest-v1"
    assert isinstance(reloaded["providers"], list)
    assert reloaded["provider_count"] == len(reloaded["providers"])
    assert reloaded["total_capability_count"] == sum(
        p["capability_count"] for p in reloaded["providers"]
    )


def test_manifest_covers_every_real_registered_builtin_provider() -> None:
    manifest = build_manifest()

    provider_names = {p["provider"] for p in manifest["providers"]}

    assert provider_names == set(_BUILTINS)


def test_sregym_capability_count_matches_the_real_source_exactly() -> None:
    """The exact regression this manifest exists to catch: a manifest whose
    sregym count silently drifts from the real, current
    SREGYM_CAPABILITIES tuple."""
    manifest = build_manifest()

    sregym_entry = next(p for p in manifest["providers"] if p["provider"] == "sregym")

    assert sregym_entry["capability_count"] == len(SREGYM_CAPABILITIES)
    assert sregym_entry["capability_count"] == 14

    manifest_bindings = {c["binding"] for c in sregym_entry["capabilities"]}
    real_bindings = {capability.binding for capability in SREGYM_CAPABILITIES}
    assert manifest_bindings == real_bindings


def test_every_capability_entry_has_the_documented_fields() -> None:
    manifest = build_manifest()

    for provider in manifest["providers"]:
        for capability in provider["capabilities"]:
            assert set(capability) == {"iri", "title", "consequence", "binding"}
            assert capability["consequence"] in {"READ", "DO"}
            assert capability["iri"]
            assert capability["binding"]


def test_main_writes_a_real_file_when_given_a_path(tmp_path: Path) -> None:
    output_path = tmp_path / "manifest.json"

    exit_code = main([str(output_path)])

    assert exit_code == 0
    assert output_path.is_file()
    written = json.loads(output_path.read_text())
    assert written["schema"] == "gymact-capability-manifest-v1"


def test_main_prints_to_stdout_with_no_path(capsys) -> None:
    exit_code = main([])

    assert exit_code == 0
    captured = capsys.readouterr()
    printed = json.loads(captured.out)
    assert printed["schema"] == "gymact-capability-manifest-v1"
