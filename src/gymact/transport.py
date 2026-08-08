"""Transport-neutral candidate-intent normalization and equivalence law."""
from __future__ import annotations

import json
from enum import StrEnum
from typing import Any, Self

from pydantic import Field, model_validator

from gymact.action_contract import PreparedAction, SubjectRef
from gymact.models import FrozenModel


class TransportKind(StrEnum):
    PYTHON = "python"
    CLI = "cli"
    REST = "rest"
    MCP = "mcp"
    A2A = "a2a"
    BPMN = "bpmn"
    POWL_V2 = "powl_v2"


class CandidateIntentEnvelope(FrozenModel):
    """A transport envelope that can carry a candidate but never execution authority."""

    transport: TransportKind
    episode_id: str = Field(min_length=1)
    action_ref: str = Field(min_length=1)
    subject: SubjectRef
    payload: dict[str, Any] = Field(default_factory=dict)
    admission_digest: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def forbid_ambient_authority(self) -> Self:
        forbidden = {
            "execution_grant",
            "executionGrant",
            "principal",
            "delegated_principal",
            "delegatedPrincipal",
            "authority_grant",
            "authorityGrant",
            "policy_revision",
            "policyRevision",
        }
        leaked = forbidden.intersection(self.metadata)
        if leaked:
            raise ValueError(f"TRANSPORT_AUTHORITY_LEAK:{sorted(leaked)}")
        return self

    def prepared(self) -> PreparedAction:
        return PreparedAction(
            episode_id=self.episode_id,
            action_ref=self.action_ref,
            subject=self.subject,
            payload=self.payload,
            admission_digest=self.admission_digest,
            idempotency_key=self.idempotency_key,
        )

    def semantic_key(self) -> str:
        """Canonical transport-independent identity; no authorization fields participate."""
        return json.dumps(
            self.prepared().model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )


def normalize_candidate(
    transport: TransportKind,
    payload: dict[str, Any],
) -> CandidateIntentEnvelope:
    """Normalize a transport payload to the same powerless candidate-intent shape."""
    values = dict(payload)
    values["transport"] = transport
    return CandidateIntentEnvelope.model_validate(values)


def protocol_equivalent(*envelopes: CandidateIntentEnvelope) -> bool:
    """True only when all protocol projections construct the same candidate intent."""
    if len(envelopes) < 2:
        raise ValueError("PROTOCOL_EQUIVALENCE_REQUIRES_MULTIPLE_TRANSPORTS")
    keys = {envelope.semantic_key() for envelope in envelopes}
    return len(keys) == 1
