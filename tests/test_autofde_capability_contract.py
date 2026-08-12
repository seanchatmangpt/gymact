"""Exact-SHA cross-repository contract court for AutoFDE's SREGym gate.

This test executes the *real AutoFDE gate source and manifest* from an
immutable public AutoFDE commit against this checkout's real
``SREGYM_CAPABILITIES`` objects. It performs no environment actuation.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

from gymact.gyms.sregym import SREGYM_CAPABILITIES
from gymact.models import Capability, Consequence

AUTOFDE_SHA = "f9a443fcf81573caccc750e5ef790883b09ab8d9"
AUTOFDE_RAW = f"https://raw.githubusercontent.com/seanchatmangpt/autofde-lab/{AUTOFDE_SHA}"


def _fetch(path: str) -> str:
    response = httpx.get(f"{AUTOFDE_RAW}/{path}", timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    return response.text


def _load_exact_autofde_gate(tmp_path: Path):
    gate_path = tmp_path / "gymact_capability_gate.py"
    gate_path.write_text(
        _fetch("src/autofde_lab/fabric/gymact_capability_gate.py"), encoding="utf-8"
    )
    manifest_path = tmp_path / "gymact_capabilities.toml"
    manifest_path.write_text(
        _fetch("src/autofde_lab/fabric/gymact_capabilities.toml"), encoding="utf-8"
    )

    module_name = "_exact_autofde_gymact_capability_gate"
    spec = importlib.util.spec_from_file_location(module_name, gate_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module, module.CapabilityGate.from_toml(manifest_path)


def test_exact_autofde_gate_matches_real_sregym_capabilities(tmp_path: Path) -> None:
    module, gate = _load_exact_autofde_gate(tmp_path)
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
