"""Portable SA2A replanning envelope consumed by GymAct.

The consequence/recovery decision is manufactured upstream by ash_a2a. This
module validates that contract and carries it as data; it deliberately contains
no outcome->recovery mapping.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import ConfigDict, Field, JsonValue, model_validator

from gymact.models import FrozenModel

SA2A_REPLAN_SCHEMA = "sa2a/replan-envelope/v1"
SA2A_REPLAN_CONTRACT_DIGEST = (
    "sha256:ff7643034ed101930e9c80df716df863b6ee6d14f3b29aff764209ad11dab80e"
)


def _finite_json(value: JsonValue) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_finite_json(item) for item in value)
    if isinstance(value, dict):
        return all(_finite_json(item) for item in value.values())
    return True


class SA2ADecision(FrozenModel):
    kind: Literal["stop", "replan"]
    reason: str = Field(min_length=1)
    authority: Literal["none"] = "none"


class SA2AReplanEnvelope(FrozenModel):
    # The portable wire key is "schema", but that name shadows pydantic's deprecated
    # `BaseModel.schema` and pydantic warns at class creation (an error under this repo's
    # filterwarnings=error, aborting collection). Keep the wire key via alias and serialize by
    # alias so `model_dump()` (hashed in `sa2a_evolution`) still emits "schema", not "schema_id".
    model_config = ConfigDict(serialize_by_alias=True)

    schema_id: Literal["sa2a/replan-envelope/v1"] = Field(
        default=SA2A_REPLAN_SCHEMA, alias="schema"
    )
    contract_digest: Literal[
        "sha256:ff7643034ed101930e9c80df716df863b6ee6d14f3b29aff764209ad11dab80e"
    ] = SA2A_REPLAN_CONTRACT_DIGEST
    exact_subject: JsonValue
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
    def exact_subject_matches_portable_schema(self) -> SA2AReplanEnvelope:
        """The producer schema admits every JSON value except null."""
        if self.exact_subject is None:
            raise ValueError("SA2A_EXACT_SUBJECT_REQUIRED")
        if not _finite_json(self.exact_subject):
            raise ValueError("SA2A_EXACT_SUBJECT_NONFINITE_NUMBER")
        return self


class SA2ARecoveryDirective(FrozenModel):
    exact_subject: JsonValue
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
