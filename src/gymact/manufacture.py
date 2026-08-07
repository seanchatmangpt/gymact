"""Dependency-neutral handoff from Python GymAct semantics to ggen/Rust manufacture."""

from __future__ import annotations

import hashlib
from pathlib import Path

from gymact.contract import build_contract
from gymact.evidence import canonical_bytes
from gymact.semantic import ExportedResource, ProfileAuthority


def export_manufacturing_bundle(directory: str | Path) -> dict[str, ExportedResource]:
    """Export profile, SHACL and canonical contract artifacts, with a real digest
    per file, for external compilers to consume and mechanically verify."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    exported = ProfileAuthority().export(target)
    contract = build_contract()
    contract_path = target / "runtime-contract.jcs.json"
    contract_bytes = canonical_bytes(contract.model_dump(mode="json"))
    contract_path.write_bytes(contract_bytes)
    exported[contract_path.name] = ExportedResource(
        path=contract_path,
        sha256=hashlib.sha256(contract_bytes).hexdigest(),
    )
    return exported
