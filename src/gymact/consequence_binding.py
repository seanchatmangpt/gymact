"""Semantic identity binding for consequential DCM morphisms."""
from __future__ import annotations

from typing import Any

from pydantic import Field

from gymact.action_contract import ActionDefinition, SubjectRef
from gymact.evidence import digest
from gymact.models import FrozenModel

_BINDING_KEY = "consequence_binding"


class ConsequenceBinding(FrozenModel):
    """Powerless identity proof that one DO edge denotes one exact semantic action."""

    action_ref: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    capability_ref: str = Field(min_length=1)
    verifier_ref: str = Field(min_length=1)
    expected_effect_digest: str = Field(min_length=1)


def expected_effect_digest(action: ActionDefinition) -> str:
    return digest([item.model_dump(mode="json") for item in action.expected_effects])


def bind_action_consequence(
    action: ActionDefinition,
    subject: SubjectRef,
) -> ConsequenceBinding:
    return ConsequenceBinding(
        action_ref=action.semantic_id,
        subject_ref=subject.semantic_id,
        capability_ref=action.capability_ref,
        verifier_ref=action.verification.observer_ref,
        expected_effect_digest=expected_effect_digest(action),
    )


def consequence_binding_attributes(binding: ConsequenceBinding) -> dict[str, Any]:
    """Encode the typed binding into powerless graph attributes."""
    return {_BINDING_KEY: binding.model_dump(mode="json")}


def read_consequence_binding(attributes: dict[str, Any]) -> ConsequenceBinding | None:
    """Read the typed binding without treating arbitrary attributes as authority."""
    raw = attributes.get(_BINDING_KEY)
    if raw is None:
        return None
    return ConsequenceBinding.model_validate(raw)
