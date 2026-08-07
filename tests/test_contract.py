from __future__ import annotations

import pytest
from pydantic import ValidationError

from gymact.contract import build_contract, contract_document
from gymact.models import ActuationIntent, Capability, Consequence, Operation
from gymact.semantic import ProfileAuthority


def test_contract_is_stable_self_identifying_and_complete() -> None:
    first = contract_document()
    second = contract_document()
    assert first == second
    assert first["version"] == "26.8.7"
    assert first["digest_algorithm"] == "BLAKE3"
    assert len(first["contract_digest"]) == 64
    assert set(first["operations"]) == {operation.value for operation in Operation}
    schemas = first["model_schemas"]
    assert "Capability" in schemas
    assert "MaterializationIntent" in schemas
    assert "ActuationIntent" in schemas
    assert "Receipt" in schemas


def test_contract_public_ontologies_match_profile_authority() -> None:
    contract = build_contract()
    assert contract.profile_uri == ProfileAuthority.profile_uri
    assert contract.public_ontologies == ProfileAuthority.public_ontologies
    assert len(contract.public_ontologies) >= 14


def test_capability_and_intent_require_absolute_semantic_iris() -> None:
    capability = Capability(
        iri="urn:test:capability:set",
        title="Set value",
        consequence=Consequence.DO,
        binding="set",
    )
    assert capability.iri.startswith("urn:")
    with pytest.raises(ValidationError):
        Capability(
            iri="relative-capability",
            title="Bad",
            consequence=Consequence.DO,
            binding="bad",
        )
    with pytest.raises(ValidationError):
        ActuationIntent(episode_id="episode", capability="not-an-iri")
