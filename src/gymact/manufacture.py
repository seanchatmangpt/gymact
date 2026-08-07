"""Dependency-neutral handoff from Python GymAct semantics to ggen/Rust manufacture."""

from __future__ import annotations

from pathlib import Path

from gymact.contract import build_contract
from gymact.evidence import canonical_bytes
from gymact.semantic import ProfileAuthority


def export_manufacturing_bundle(directory: str | Path) -> dict[str, Path]:
    """Export profile, SHACL and canonical contract artifacts for external compilers."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    exported = ProfileAuthority().export(target)
    contract = build_contract()
    contract_path = target / "runtime-contract.jcs.json"
    contract_path.write_bytes(canonical_bytes(contract.model_dump(mode="json")))
    exported[contract_path.name] = contract_path
    return exported
