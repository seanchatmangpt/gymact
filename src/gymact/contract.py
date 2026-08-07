"""Portable semantic/runtime contract for cross-language manufacture."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from gymact.evidence import digest
from gymact.models import ActuationIntent, MaterializationIntent, Operation, Receipt, VerificationResult
from gymact.semantic import ProfileAuthority

PUBLIC_SEMANTICS = (
    "http://www.w3.org/ns/dx/prof/",
    "http://www.w3.org/ns/prov#",
    "http://purl.org/net/p-plan#",
    "http://www.w3.org/ns/sosa/",
    "https://www.w3.org/2019/wot/td#",
    "http://www.w3.org/ns/odrl/2/",
    "http://www.w3.org/ns/shacl#",
    "http://www.w3.org/ns/earl#",
    "http://www.w3.org/ns/dqv#",
    "http://qudt.org/schema/qudt/",
    "http://www.w3.org/ns/dcat#",
    "http://www.w3.org/2004/02/skos/core#",
    "http://www.w3.org/2006/time#",
    "http://purl.org/dc/terms/",
)


class RuntimeContract(BaseModel):
    """Stable contract consumable by ggen, Rust/WIT/WASM or independent checkers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gymact_version: str
    profile_uri: str
    canonicalization: str
    digest_algorithm: str
    operations: tuple[str, ...]
    surfaces: tuple[str, ...]
    public_semantics: tuple[str, ...]
    schemas: dict[str, dict[str, object]]
    contract_digest: str

    def verify_digest(self) -> bool:
        """Recompute the contract digest without trusting the stored value."""
        payload = self.model_dump(mode="json", exclude={"contract_digest"})
        return digest(payload) == self.contract_digest


def build_contract(version: str = "26.8.7") -> RuntimeContract:
    """Build and self-digest the admitted Python runtime contract."""
    payload = {
        "gymact_version": version,
        "profile_uri": ProfileAuthority.profile_uri,
        "canonicalization": "RFC8785-JCS",
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
            "rdf",
        ),
        "public_semantics": PUBLIC_SEMANTICS,
        "schemas": {
            "materialization_intent": MaterializationIntent.model_json_schema(),
            "actuation_intent": ActuationIntent.model_json_schema(),
            "verification_result": VerificationResult.model_json_schema(),
            "receipt": Receipt.model_json_schema(),
        },
    }
    return RuntimeContract(**payload, contract_digest=digest(payload))
