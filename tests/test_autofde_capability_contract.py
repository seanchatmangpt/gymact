"""Exact-SHA cross-repository contract court for AutoFDE's SREGym gate.

This test executes the real AutoFDE gate source and manifest vendored from an
immutable public AutoFDE commit against this checkout's real
``SREGYM_CAPABILITIES`` objects. It performs no environment actuation.

Provenance: the two vendored files were copied byte-identical from the local
canonical autofde-lab checkout (verified against ``git show <sha>:<path>``
for each file's last-change commit before landing) and are pinned per-file:

- ``gymact_capabilities.toml``  -> autofde-lab@09e65693bf234f9a147385aa9299c0e4db7d30f5
  (2026-08-12; re-verified 14-capability manifest)
- ``gymact_capability_gate.py`` -> autofde-lab@814615fa14646710de2c2f507b96c34d4a42874f
  (2026-09-22)

The prior version of this test refetched both files from GitHub raw at a
repo commit (f9a443fc) that predated the manifest's 2026-08-12 re-verification,
so the exact-SHA court was verifying against stale content. The vendored
local byte-pin removes the network dependency; the freshness court below
makes any future autofde-lab drift visible instead of silent.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from gymact.gyms.sregym import SREGYM_CAPABILITIES
from gymact.models import Capability, Consequence

TESTS_DIR = Path(__file__).resolve().parent
VENDOR_DIR = TESTS_DIR / "fixtures" / "autofde"
AUTOFDE_CHECKOUT = Path("/Users/sac/autofde-lab")

# Per-file exact pins: last autofde-lab commit that touched each vendored file.
AUTOFDE_TOML_SHA = "09e65693bf234f9a147385aa9299c0e4db7d30f5"
AUTOFDE_GATE_SHA = "814615fa14646710de2c2f507b96c34d4a42874f"
# autofde-lab repo HEAD the vendored bytes were taken from (provenance only).
AUTOFDE_VENDOR_HEAD_SHA = "7d4574dd8385a5f111e4b8dec016c5afe7a9f0fb"


def _load_exact_autofde_gate():
    gate_path = VENDOR_DIR / "gymact_capability_gate.py"
    manifest_path = VENDOR_DIR / "gymact_capabilities.toml"
    assert gate_path.is_file(), f"missing vendored gate: {gate_path}"
    assert manifest_path.is_file(), f"missing vendored manifest: {manifest_path}"

    module_name = "_exact_autofde_gymact_capability_gate"
    spec = importlib.util.spec_from_file_location(module_name, gate_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module, module.CapabilityGate.from_toml(manifest_path)


def test_exact_autofde_gate_matches_real_sregym_capabilities() -> None:
    module, gate = _load_exact_autofde_gate()
    real_names = frozenset(capability.binding for capability in SREGYM_CAPABILITIES)

    assert len(SREGYM_CAPABILITIES) == 14
    assert gate.environment == "sregym"
    assert gate.allowed_names == real_names
    assert gate.stale_entries(real_names) == frozenset()
    for capability in SREGYM_CAPABILITIES:
        assert gate.guard_capability(capability) is capability

    ground_truth = Capability(
        iri="urn:gymact:sregym:capability:get_injected_fault",
        title="Hypothetical grading-only ground-truth read",
        consequence=Consequence.READ,
        binding="get_injected_fault",
    )
    with pytest.raises(module.CapabilityRefused, match="CAPABILITY_NOT_IN_MANIFEST"):
        gate.guard_capability(ground_truth)


def test_vendored_autofde_files_match_autofde_lab_head() -> None:
    """Freshness court: vendored bytes must equal the canonical autofde-lab
    checkout's working tree. If autofde-lab moves, this fails with an exact
    diff, forcing a deliberate re-vendor + re-pin (drift visible, not silent).
    Skipped when the canonical checkout is not present (e.g. CI without it).
    """
    if not AUTOFDE_CHECKOUT.is_dir():
        pytest.skip(
            f"canonical autofde-lab checkout not present at {AUTOFDE_CHECKOUT}"
        )
    for filename in ("gymact_capabilities.toml", "gymact_capability_gate.py"):
        vendored = (VENDOR_DIR / filename).read_bytes()
        upstream = (AUTOFDE_CHECKOUT / "src/autofde_lab/fabric" / filename).read_bytes()
        assert vendored == upstream, (
            f"vendored {filename} drifted from autofde-lab working tree "
            f"(vendored pin: toml={AUTOFDE_TOML_SHA[:12]}, "
            f"gate={AUTOFDE_GATE_SHA[:12]}, head={AUTOFDE_VENDOR_HEAD_SHA[:12]}). "
            "Re-vendor from the current autofde-lab HEAD and update the pins."
        )
