"""Dependency-neutral handoff from Python GymAct semantics to ggen/Rust manufacture."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from gymact.contract import build_contract
from gymact.evidence import canonical_bytes
from gymact.semantic import ExportedResource, ProfileAuthority
from gymact.synthetic_ocel import OCELGymResult, manufacture_ocel_history


def synthetic_ocel_manufacturing_contract() -> dict[str, Any]:
    """Machine-readable contract for GGen's synthetic OCEL result projection.

    The generated history is allowed to be operationally indistinguishable
    from an executed/observed history, but privileged provenance must remain
    distinguishable and the projection can never mint execution evidence.
    """

    return {
        "schema": "urn:gymact:synthetic-ocel-result:v1",
        "canonical_result": "OCEL_2_0",
        "generator_role": "ggen",
        "operational_projection": "ocel_only",
        "audit_projection": "ocel_plus_provenance",
        "manufactured_origin": "GGEN_MANUFACTURED",
        "required_provenance": [
            "observed_execution=false",
            "manufactured_trace=true",
            "claimed_actor",
            "generator",
            "generator_spec_digest",
            "world_model_digest",
            "seed",
            "trace_digest",
        ],
        "forbidden": [
            "execution_receipt",
            "observed_execution=true",
            "execution_standing",
            "ambient_actuation_authority",
        ],
    }


def manufacture_synthetic_ocel_result(
    *,
    history_spec: Mapping[str, Any],
    claimed_actor: str,
    generator_spec: Any,
    world_model: Any,
    seed: int | str,
    generator: str = "ggen",
    cursor: str | None = None,
) -> OCELGymResult:
    """Public manufacture entrypoint used by GGen projections and packs."""

    return manufacture_ocel_history(
        history_spec=history_spec,
        claimed_actor=claimed_actor,
        generator_spec=generator_spec,
        world_model=world_model,
        seed=seed,
        generator=generator,
        cursor=cursor,
    )


def export_manufacturing_bundle(directory: str | Path) -> dict[str, ExportedResource]:
    """Export semantic/runtime contracts for external compilers to consume."""

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

    synthetic_contract = synthetic_ocel_manufacturing_contract()
    synthetic_path = target / "synthetic-ocel-result-contract.jcs.json"
    synthetic_bytes = canonical_bytes(synthetic_contract)
    synthetic_path.write_bytes(synthetic_bytes)
    exported[synthetic_path.name] = ExportedResource(
        path=synthetic_path,
        sha256=hashlib.sha256(synthetic_bytes).hexdigest(),
    )

    return exported
