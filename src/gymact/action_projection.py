"""Digest-bound projections from the canonical :class:`ActionDefinition`.

`ActionDefinition` is the semantic source. Every object in this module is a
powerless, deterministic projection of that source; no projection can mint an
`ExecutionGrant` or cross the BRCE DO boundary.
"""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import Field, model_validator

from gymact.action_contract import ActionDefinition, SubjectRef
from gymact.action_graph import action_possibility_fragment
from gymact.combinatorial import PossibilityGraph
from gymact.evidence import digest
from gymact.models import Capability, Consequence, FrozenModel
from gymact.world import AffordanceKind, Move


ACTION_CONTRACT_SCHEMA = "urn:gymact:action-contract:v1"
ACTION_MANUFACTURE_SCHEMA = "urn:gymact:action-manufacture-projection:v1"


def _action_contract_digest(action: ActionDefinition) -> str:
    return digest(
        {
            "schema": ACTION_CONTRACT_SCHEMA,
            "action": action.model_dump(mode="json"),
            "do_authority": False,
        }
    )


class CanonicalActionContract(FrozenModel):
    """Content-addressed wrapper proving which `ActionDefinition` was projected."""

    schema: Literal["urn:gymact:action-contract:v1"] = ACTION_CONTRACT_SCHEMA
    action: ActionDefinition
    contract_digest: str = Field(min_length=1)
    do_authority: Literal[False] = False

    @classmethod
    def from_action(cls, action: ActionDefinition) -> "CanonicalActionContract":
        return cls(action=action, contract_digest=_action_contract_digest(action))

    @model_validator(mode="after")
    def verify_digest(self) -> Self:
        if self.contract_digest != _action_contract_digest(self.action):
            raise ValueError("ACTION_CONTRACT_DIGEST_MISMATCH")
        return self


class ActionManufactureProjection(FrozenModel):
    """Powerless manufacture handoff derived from one canonical action contract."""

    schema: Literal["urn:gymact:action-manufacture-projection:v1"] = ACTION_MANUFACTURE_SCHEMA
    source_contract_digest: str = Field(min_length=1)
    action_ref: str = Field(min_length=1)
    provider_ref: str = Field(min_length=1)
    capability_ref: str = Field(min_length=1)
    subject_type: str = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] = Field(default_factory=dict)
    expected_effects: tuple[dict[str, Any], ...]
    verifier_ref: str = Field(min_length=1)
    verification: dict[str, Any]
    do_authority: Literal[False] = False


def project_capability(contract: CanonicalActionContract) -> Capability:
    """Project the action into GymAct's public capability carrier."""
    action = contract.action
    return Capability(
        iri=action.capability_ref,
        title=action.semantic_id,
        consequence=Consequence.DO,
        binding=action.provider_ref,
    )


def project_move(contract: CanonicalActionContract, *, subject_ref: str) -> Move:
    """Project one consequential world move without granting execution authority."""
    action = contract.action
    return Move(
        subject_ref=subject_ref,
        affordance=action.semantic_id,
        kind=AffordanceKind.EFFECT,
        capability_ref=action.capability_ref,
        input_schema=action.input_schema,
        description=f"Canonical action {action.semantic_id}; consequence requires BRCE.",
    )


def project_possibility_graph(
    contract: CanonicalActionContract,
    *,
    subject: SubjectRef,
) -> PossibilityGraph:
    """Project the same action into the canonical DfCM possibility topology."""
    return action_possibility_fragment(contract.action, subject)


def project_manufacture(contract: CanonicalActionContract) -> ActionManufactureProjection:
    """Project a digest-bound CONSTRUCT-only handoff for deterministic manufacture."""
    action = contract.action
    return ActionManufactureProjection(
        source_contract_digest=contract.contract_digest,
        action_ref=action.semantic_id,
        provider_ref=action.provider_ref,
        capability_ref=action.capability_ref,
        subject_type=action.subject_type,
        input_schema=action.input_schema,
        output_schema=action.output_schema,
        expected_effects=tuple(
            effect.model_dump(mode="json") for effect in action.expected_effects
        ),
        verifier_ref=action.verification.observer_ref,
        verification=action.verification.model_dump(mode="json"),
    )
