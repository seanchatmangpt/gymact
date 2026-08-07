"""Canonical Pydantic runtime realization of GymAct's public semantic profile."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, TypeAlias
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    PositiveFloat,
    PositiveInt,
    field_validator,
)

JsonObject: TypeAlias = dict[str, JsonValue]


def _absolute_iri(value: str) -> str:
    """Require a non-empty absolute IRI-like identifier without normalizing it."""
    if not value or any(character.isspace() for character in value):
        raise ValueError("must be a non-empty absolute IRI without whitespace")
    if not urlsplit(value).scheme:
        raise ValueError("must be an absolute IRI with a scheme")
    return value


def _optional_absolute_iri(value: str | None) -> str | None:
    return _absolute_iri(value) if value is not None else None


class Standing(StrEnum):
    """Evidence-aware standing for a runtime result."""

    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    ALIVE = "ALIVE"
    BLOCKED = "BLOCKED"
    BUILD_BROKEN = "BUILD_BROKEN"
    UNSUPPORTED = "UNSUPPORTED"
    REFUSED = "REFUSED"


class Consequence(StrEnum):
    """Public-profile consequence classification for a capability."""

    READ = "READ"
    DO = "DO"


class Operation(StrEnum):
    """Operations the v26.8.7 generic runtime actually executes."""

    DISCOVER = "discover"
    MATERIALIZE = "materialize"
    OBSERVE = "observe"
    ACT = "act"
    VERIFY = "verify"
    CHECKPOINT = "checkpoint"
    RESTORE = "restore"
    TEARDOWN = "teardown"


class ReceiptStage(StrEnum):
    """Write-ahead versus terminal evidence stage."""

    PREPARED = "PREPARED"
    FINAL = "FINAL"


class FrozenModel(BaseModel):
    """Strict immutable model base for receipts and externally visible values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RuntimeLimits(FrozenModel):
    """Bound external effects and untrusted payload/state sizes."""

    provider_timeout_s: PositiveFloat = 30.0
    authority_timeout_s: PositiveFloat = 10.0
    max_payload_bytes: PositiveInt = 1_048_576
    max_state_bytes: PositiveInt = 16_777_216


class Capability(FrozenModel):
    """Python realization of a public ``sosa:Procedure`` capability.

    ``iri`` is semantic identity. ``binding`` is provider-local execution data and
    deliberately does not define the capability's meaning.
    """

    iri: str
    title: str = Field(min_length=1, max_length=512)
    consequence: Consequence
    binding: str = Field(min_length=1, max_length=256)

    _validate_iri = field_validator("iri")(_absolute_iri)


class Episode(FrozenModel):
    """One bounded attempt against one materialized environment."""

    episode_id: str = Field(min_length=1, max_length=256)
    provider: str = Field(min_length=1, max_length=256)
    environment_id: str = Field(min_length=1, max_length=2048)
    scenario: str | None = Field(default=None, max_length=2048)
    standing: Standing = Standing.ALIVE

    _validate_environment_id = field_validator("environment_id")(_absolute_iri)


class Observation(FrozenModel):
    """Evidence about an environment, not the environment itself."""

    episode_id: str
    state: JsonObject
    state_digest: str


class AuthorityRequest(FrozenModel):
    """Question submitted to an external authority resolver before consequential DO."""

    episode_id: str
    subject_ref: str
    operation: Operation
    capability_ref: str
    payload: JsonObject = Field(default_factory=dict)
    authority_ref: str | None = None

    _validate_subject_ref = field_validator("subject_ref")(_absolute_iri)
    _validate_capability_ref = field_validator("capability_ref")(_absolute_iri)
    _validate_authority_ref = field_validator("authority_ref")(_optional_absolute_iri)


class AuthorityDecision(FrozenModel):
    """Authority resolver verdict; a reference alone never implies admission."""

    admitted: bool
    reason: str = Field(pattern=r"^[A-Z0-9_.:-]{1,128}$")
    evidence_ref: str | None = None
    error_type: str | None = Field(default=None, max_length=256)
    error_digest: str | None = None

    _validate_evidence_ref = field_validator("evidence_ref")(_optional_absolute_iri)


class MaterializationIntent(FrozenModel):
    """Request to create one bounded environment episode."""

    provider: str = Field(default="memory", min_length=1, max_length=256)
    scenario: str | None = Field(default=None, max_length=2048)
    config: JsonObject = Field(default_factory=dict)
    authority_ref: str | None = None
    idempotency_key: str = Field(
        default_factory=lambda: uuid4().hex, min_length=1, max_length=256
    )
    operation: Literal[Operation.MATERIALIZE] = Operation.MATERIALIZE

    _validate_authority_ref = field_validator("authority_ref")(_optional_absolute_iri)


class ActuationIntent(FrozenModel):
    """Requested consequential capability invocation. It never grants authority."""

    episode_id: str = Field(min_length=1, max_length=256)
    capability: str
    payload: JsonObject = Field(default_factory=dict)
    authority_ref: str | None = None
    idempotency_key: str = Field(
        default_factory=lambda: uuid4().hex, min_length=1, max_length=256
    )
    operation: Literal[Operation.ACT] = Operation.ACT

    _validate_capability = field_validator("capability")(_absolute_iri)
    _validate_authority_ref = field_validator("authority_ref")(_optional_absolute_iri)


class VerificationResult(FrozenModel):
    """Independent predicate result over observed state."""

    verification_id: str = Field(default_factory=lambda: uuid4().hex)
    episode_id: str
    passed: bool
    expected: JsonObject
    observed: JsonObject
    state_digest: str
    receipt_id: str | None = None


class Score(FrozenModel):
    """Benchmark-native metric value; scoring remains distinct from verification."""

    metric: str = Field(min_length=1, max_length=256)
    value: float
    unit: str = Field(default="1", min_length=1, max_length=128)
    details: JsonObject = Field(default_factory=dict)


class Receipt(FrozenModel):
    """Bounded causal evidence for one operation.

    Raw provider output and exception text are intentionally excluded. A receipt
    ledger stamps ``previous_receipt_digest`` and ``receipt_digest`` to form a
    tamper-evident BLAKE3 chain. Consequential provider calls receive a PREPARED
    receipt before invocation and a FINAL receipt afterward.
    """

    receipt_id: str = Field(default_factory=lambda: uuid4().hex)
    episode_id: str
    operation: Operation
    stage: ReceiptStage = ReceiptStage.FINAL
    standing: Standing
    occurred_at: datetime | None = None
    subject_ref: str | None = None
    capability_ref: str | None = None
    authority_ref: str | None = None
    authority_evidence_ref: str | None = None
    idempotency_key: str | None = None
    pre_state_digest: str | None = None
    post_state_digest: str | None = None
    verification_id: str | None = None
    prepared_receipt_digest: str | None = None
    reason: str | None = Field(default=None, pattern=r"^[A-Z0-9_.:-]{1,128}$")
    error_type: str | None = Field(default=None, max_length=256)
    error_digest: str | None = None
    previous_receipt_digest: str | None = None
    receipt_digest: str | None = None

    _validate_subject_ref = field_validator("subject_ref")(_optional_absolute_iri)
    _validate_capability_ref = field_validator("capability_ref")(_optional_absolute_iri)
    _validate_authority_ref = field_validator("authority_ref")(_optional_absolute_iri)
    _validate_authority_evidence_ref = field_validator("authority_evidence_ref")(
        _optional_absolute_iri
    )


class MaterializationResult(FrozenModel):
    """Disposition of environment materialization, including refused/blocked setup."""

    accepted: bool
    standing: Standing
    episode: Episode | None = None
    observation: Observation | None = None
    receipt: Receipt


class ActuationResult(FrozenModel):
    """Actuation disposition plus independently observable consequence evidence."""

    accepted: bool
    standing: Standing
    effect: JsonObject | None = None
    observation: Observation | None = None
    receipt: Receipt


class VerifyRequest(BaseModel):
    """Expected partial state for independent verification."""

    model_config = ConfigDict(extra="forbid")
    expected: JsonObject


class RestoreRequest(BaseModel):
    """Checkpoint payload for deterministic restore."""

    model_config = ConfigDict(extra="forbid")
    checkpoint: JsonObject


class ContractBundle(FrozenModel):
    """Portable semantic/runtime contract for ggen and other independent compilers."""

    version: str
    profile_uri: str
    digest_algorithm: Literal["BLAKE3"] = "BLAKE3"
    operations: tuple[Operation, ...]
    public_ontologies: tuple[str, ...]
    model_schemas: dict[str, JsonObject]
