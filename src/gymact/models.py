"""Canonical Pydantic runtime realization of GymAct's public semantic profile."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, Self
from uuid import uuid4

import rfc8785
from pydantic import BaseModel, ConfigDict, Field, model_validator


def _utc_now_iso() -> str:
    """Real UTC timestamp, OCEL-2.0-compliant (`ocel:timestamp` requires
    ISO 8601 date-time). Not a fixed/frozen clock -- every `Receipt` really
    records when it was minted."""
    return datetime.now(UTC).isoformat()


class Standing(StrEnum):
    """Evidence-aware standing for a runtime result.

    The positive ladder is UNKNOWN < CANDIDATE < STRUCTURAL < PARTIAL_ALIVE <
    ALIVE < ADOPTED. The remaining values are orthogonal dispositions and do
    not imply a position on that ladder.
    """

    UNKNOWN = "UNKNOWN"
    CANDIDATE = "CANDIDATE"
    STRUCTURAL = "STRUCTURAL"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    ALIVE = "ALIVE"
    ADOPTED = "ADOPTED"
    BLOCKED = "BLOCKED"
    BUILD_BROKEN = "BUILD_BROKEN"
    UNSUPPORTED = "UNSUPPORTED"
    REQUIRES_CONFIGURATION = "REQUIRES_CONFIGURATION"
    REFUSED = "REFUSED"
    UNCERTAIN = "UNCERTAIN"
    STALE = "STALE"


class Consequence(StrEnum):
    """Public-profile consequence classification for a capability."""

    READ = "READ"
    DO = "DO"


class Operation(StrEnum):
    """Operations the v26.8.7 generic runtime actually executes.

    Deliberately 8, not the earlier ontology work's full 12-operation model
    (which also named `configure`, `reset`, `start`, `score`). A Reduce
    decision, not an unfinished 12-op ambition: for the current provider set
    (all three real gym providers -- CUBE counter, its container variant,
    the ggen-legacy verifier -- are stateless-enough per episode) `configure`
    /`reset`/`start` add no information beyond what `materialize` already
    captures, so a separate operation for each would be pure ceremony. And
    `score` would duplicate `VerificationResult.passed`, which every real
    full-lifecycle test already treats as the pass/fail signal. Revisit only
    if a future gym family genuinely needs configuration separate from
    materialization, or a scalar score distinct from verification.
    """

    DISCOVER = "discover"
    MATERIALIZE = "materialize"
    OBSERVE = "observe"
    ACT = "act"
    VERIFY = "verify"
    CHECKPOINT = "checkpoint"
    RESTORE = "restore"
    TEARDOWN = "teardown"


class FrozenModel(BaseModel):
    """Strict immutable model base for receipts and externally visible values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CanonicalInputModel(FrozenModel):
    """Input model that must have one RFC8785 representation across runtimes."""

    @model_validator(mode="after")
    def require_canonical_json(self) -> Self:
        try:
            rfc8785.dumps(self.model_dump(mode="python"))
        except (rfc8785.CanonicalizationError, TypeError, ValueError) as exc:
            raise ValueError("INPUT_NOT_RFC8785_CANONICAL") from exc
        return self


class Capability(FrozenModel):
    """Python realization of a public ``sosa:Procedure`` capability.

    ``iri`` is semantic identity. ``binding`` is provider-local execution data and
    deliberately does not define the capability's meaning.
    """

    iri: str
    title: str
    consequence: Consequence
    binding: str


class Episode(FrozenModel):
    """One bounded attempt against one materialized environment."""

    episode_id: str
    provider: str
    environment_id: str
    scenario: str | None = None
    standing: Standing = Standing.ALIVE


class Observation(FrozenModel):
    """Evidence about an environment, not the environment itself."""

    episode_id: str
    state: dict[str, Any]
    state_digest: str


class AuthorityRequest(CanonicalInputModel):
    """Question submitted to an external authority resolver before consequential DO."""

    episode_id: str
    subject_ref: str
    operation: Operation
    capability_ref: str
    payload: dict[str, Any] = Field(default_factory=dict)
    authority_ref: str | None = None


class AuthorityDecision(FrozenModel):
    """Authority resolver verdict; a reference alone never implies admission."""

    admitted: bool
    reason: str
    evidence_ref: str | None = None


class MaterializationIntent(CanonicalInputModel):
    """Request to create one bounded environment episode."""

    provider: str = "memory"
    scenario: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    authority_ref: str | None = None
    idempotency_key: str = Field(default_factory=lambda: uuid4().hex)
    operation: Literal[Operation.MATERIALIZE] = Operation.MATERIALIZE


class ActuationIntent(CanonicalInputModel):
    """Requested consequential capability invocation. It never grants authority."""

    episode_id: str
    capability: str
    payload: dict[str, Any] = Field(default_factory=dict)
    authority_ref: str | None = None
    idempotency_key: str = Field(default_factory=lambda: uuid4().hex)
    operation: Literal[Operation.ACT] = Operation.ACT


class VerificationResult(FrozenModel):
    """Independent predicate result over observed state."""

    verification_id: str = Field(default_factory=lambda: uuid4().hex)
    episode_id: str
    passed: bool
    expected: dict[str, Any]
    observed: dict[str, Any]
    state_digest: str


class Score(FrozenModel):
    """Benchmark-native metric value; scoring remains distinct from verification."""

    metric: str
    value: float
    unit: str = "1"


class Receipt(FrozenModel):
    """Bounded causal evidence for one accepted, blocked, or refused operation."""

    receipt_id: str = Field(default_factory=lambda: uuid4().hex)
    occurred_at: str = Field(default_factory=_utc_now_iso)
    episode_id: str
    operation: Operation
    standing: Standing
    subject_ref: str | None = None
    capability_ref: str | None = None
    authority_ref: str | None = None
    authority_evidence_ref: str | None = None
    idempotency_key: str | None = None
    pre_state_digest: str | None = None
    post_state_digest: str | None = None
    verification_id: str | None = None
    error_digest: str | None = None
    reason: str | None = None


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
    effect: dict[str, Any] | None = None
    observation: Observation | None = None
    receipt: Receipt


class VerifyRequest(CanonicalInputModel):
    """Expected partial state for independent verification."""

    expected: dict[str, Any]


class RestoreRequest(CanonicalInputModel):
    """Checkpoint payload for deterministic restore."""

    checkpoint: dict[str, Any]
