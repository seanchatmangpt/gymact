"""Typed runtime models for GymAct's Python reference implementation."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Standing(StrEnum):
    """Evidence-aware standing for a runtime result."""

    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    ALIVE = "ALIVE"
    BLOCKED = "BLOCKED"
    BUILD_BROKEN = "BUILD_BROKEN"
    UNSUPPORTED = "UNSUPPORTED"
    REFUSED = "REFUSED"


class Operation(StrEnum):
    """Reference lifecycle operations derived from the semantic profile."""

    DISCOVER = "discover"
    MATERIALIZE = "materialize"
    CONFIGURE = "configure"
    RESET = "reset"
    START = "start"
    OBSERVE = "observe"
    ACT = "act"
    VERIFY = "verify"
    SCORE = "score"
    CHECKPOINT = "checkpoint"
    RESTORE = "restore"
    TEARDOWN = "teardown"


class FrozenModel(BaseModel):
    """Strict immutable model base for receipts and externally visible values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


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


class ActuationIntent(FrozenModel):
    """Requested actuation. Constructing it never grants authority."""

    episode_id: str
    affordance: str
    payload: dict[str, Any] = Field(default_factory=dict)
    authority_ref: str | None = None
    idempotency_key: str = Field(default_factory=lambda: uuid4().hex)
    operation: Operation = Operation.ACT


class VerificationResult(FrozenModel):
    """Independent predicate result over observed state."""

    verification_id: str = Field(default_factory=lambda: uuid4().hex)
    episode_id: str
    passed: bool
    expected: dict[str, Any]
    observed: dict[str, Any]
    state_digest: str


class Score(FrozenModel):
    """Benchmark-compatible metric value kept separate from verification."""

    metric: str
    value: float
    unit: str = "1"


class Receipt(FrozenModel):
    """Bounded causal evidence for one accepted or refused operation."""

    receipt_id: str = Field(default_factory=lambda: uuid4().hex)
    episode_id: str
    operation: Operation
    standing: Standing
    affordance: str | None = None
    authority_ref: str | None = None
    idempotency_key: str | None = None
    pre_state_digest: str | None = None
    post_state_digest: str | None = None
    verification_id: str | None = None
    reason: str | None = None


class ActuationResult(FrozenModel):
    """Actuation disposition plus independently observable consequence evidence."""

    accepted: bool
    standing: Standing
    effect: dict[str, Any] | None = None
    observation: Observation | None = None
    receipt: Receipt


class CreateEpisodeRequest(BaseModel):
    """HTTP/MCP request for a bounded environment episode."""

    model_config = ConfigDict(extra="forbid")
    provider: str = "memory"
    scenario: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class VerifyRequest(BaseModel):
    """Expected partial state for independent verification."""

    model_config = ConfigDict(extra="forbid")
    expected: dict[str, Any]


class RestoreRequest(BaseModel):
    """Checkpoint payload for deterministic restore."""

    model_config = ConfigDict(extra="forbid")
    checkpoint: dict[str, Any]
