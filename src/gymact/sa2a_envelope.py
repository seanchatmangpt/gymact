"""Portable SA2A replanning envelope consumed by GymAct.

The consequence/recovery decision is manufactured upstream by ash_a2a. This
module validates that contract and carries it as data; it deliberately contains
no outcome->recovery mapping.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, model_validator

from gymact.models import FrozenModel

SA2A_REPLAN_SCHEMA = "sa2a/replan-envelope/v1"
SA2A_REPLAN_CONTRACT_DIGEST = (
    "sha256:ff7643034ed101930e9c80df716df863b6ee6d14f3b29aff764209ad11dab80e"
)


class SA2ADecision(FrozenModel):
    kind: Literal["stop", "replan"]
    reason: str = Field(min_length=1)
    authority: Literal["none"] = "none"


class SA2AReplanEnvelope(FrozenModel):
    schema: Literal["sa2a/replan-envelope/v1"] = SA2A_REPLAN_SCHEMA
    contract_digest: Literal[
        "sha256:ff7643034ed101930e9c80df716df863b6ee6d14f3b29aff764209ad11dab80e"
    ] = SA2A_REPLAN_CONTRACT_DIGEST
    exact_subject: Any
    receipt_id: str = Field(min_length=1)
    consequence: Literal[
        "executed",
        "failed",
        "refused",
        "reconciled",
        "compensated",
        "unknown_outcome",
    ]
    decision: SA2ADecision
    provider: str | None = None
    projection_digest: str | None = None
    source_replay_key: str | None = None

    @model_validator(mode="after")
    def exact_subject_matches_portable_schema(self) -> "SA2AReplanEnvelope":
        """The producer schema admits any non-null JSON exact-subject value."""
        if self.exact_subject is None:
            raise ValueError("SA2A_EXACT_SUBJECT_REQUIRED")
        try:
            json.dumps(self.exact_subject, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("SA2A_EXACT_SUBJECT_NOT_JSON") from exc
        return self


class SA2ARecoveryDirective(FrozenModel):
    exact_subject: Any
    receipt_id: str = Field(min_length=1)
    consequence: str = Field(min_length=1)
    kind: Literal["stop", "replan"]
    reason: str = Field(min_length=1)
    authority: Literal["none"] = "none"
    provider: str | None = None


def admit_envelope(value: SA2AReplanEnvelope | dict[str, object]) -> SA2AReplanEnvelope:
    """Validate the exact canonical SA2A portable contract."""
    if isinstance(value, SA2AReplanEnvelope):
        return value
    return SA2AReplanEnvelope.model_validate(value)
