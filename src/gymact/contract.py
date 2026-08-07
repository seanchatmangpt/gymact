"""Portable contract export for ggen and independent ecosystem compilers."""

from __future__ import annotations

from gymact.evidence import digest_json
from gymact.models import (
    ActuationIntent,
    ActuationResult,
    AuthorityDecision,
    AuthorityRequest,
    Capability,
    ContractBundle,
    Episode,
    MaterializationIntent,
    MaterializationResult,
    Observation,
    Operation,
    Receipt,
    RuntimeLimits,
    Score,
    VerificationResult,
)
from gymact.semantic import ProfileAuthority

_MODEL_TYPES = (
    Capability,
    Episode,
    Observation,
    AuthorityRequest,
    AuthorityDecision,
    MaterializationIntent,
    MaterializationResult,
    ActuationIntent,
    ActuationResult,
    VerificationResult,
    Score,
    Receipt,
    RuntimeLimits,
)


def build_contract() -> ContractBundle:
    """Build the canonical JSON-schema contract from Python's semantic realization."""
    return ContractBundle(
        version="26.8.7",
        profile_uri=ProfileAuthority.profile_uri,
        operations=tuple(Operation),
        public_ontologies=ProfileAuthority.public_ontologies,
        model_schemas={model.__name__: model.model_json_schema() for model in _MODEL_TYPES},
    )


def contract_document() -> dict[str, object]:
    """Return a self-identifying JSON-compatible contract document."""
    contract = build_contract().model_dump(mode="json")
    return {**contract, "contract_digest": digest_json(contract)}
