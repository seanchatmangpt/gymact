"""Portable semantic/runtime contract for cross-language manufacture."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from gymact.evidence import digest
from gymact.models import ActuationIntent, MaterializationIntent, Operation, Receipt, VerificationResult
from gymact.semantic import ProfileAuthority


class RuntimeContract(BaseModel):
    """Stable contract consumable by ggen, Rust/WIT/WASM or independent checkers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gymact_version: str
    profile_uri: str
    digest_algorithm: str
    operations: tuple[str, ...]
    surfaces: tuple[str, ...]
    schemas: dict[str, dict[str, object]]
    contract_digest: str


def build_contract(version: str = "26.8.7") -> RuntimeContract:
    """Build and self-digest the admitted Python runtime contract."""
    payload = {
        "gymact_version": version,
        "profile_uri": ProfileAuthority.profile_uri,
        "digest_algorithm": "blake3-256",
        "operations": tuple(operation.value for operation in Operation),
        "surfaces": (
            "python",
            "pydantic",
            "fastapi",
            "openapi",
            "fastmcp",
            "typer",
            "faststream",
        ),
        "schemas": {
            "materialization_intent": MaterializationIntent.model_json_schema(),
            "actuation_intent": ActuationIntent.model_json_schema(),
            "verification_result": VerificationResult.model_json_schema(),
            "receipt": Receipt.model_json_schema(),
        },
    }
    return RuntimeContract(**payload, contract_digest=digest(payload))
