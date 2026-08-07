"""Canonical Pydantic models for GymAct.

These are the single source of typed truth for every surface (CLI, and future
FastAPI/FastMCP/FastStream surfaces per .claude/rules/python-native.md). They mirror
the semantic profile in gymact/semantic/profile.ttl: `Consequence` mirrors the two
SKOS concepts gymact:consequence-read / gymact:consequence-do, and `Capability`
mirrors a sosa:Procedure instance conforming to gymact:CapabilityShape.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

__all__ = [
    "ActuationResult",
    "Capability",
    "Consequence",
    "Intent",
    "Standing",
]


class Consequence(StrEnum):
    """Whether invoking a capability requires actuation authority.

    See .claude/rules/actuation-authority.md.
    """

    READ = "read"
    DO = "do"


class Capability(BaseModel):
    """A capability a gym exposes, corresponding to a sosa:Procedure instance."""

    id: str
    title: str
    consequence: Consequence


class Intent(BaseModel):
    """A requested invocation of a capability. Never itself authority to act."""

    capability_id: str
    payload: dict[str, object] = Field(default_factory=dict)
    authority_ref: str | None = None
    idempotency_key: str


class Standing(StrEnum):
    """Disposition of an actuation attempt."""

    ACCEPTED = "accepted"
    REFUSED = "refused"


class ActuationResult(BaseModel):
    """Outcome of an actuation attempt, binding intent to pre/post state.

    A `standing` of REFUSED with a `reason` is a first-class, typed outcome — never a
    silent no-op. See .claude/rules/actuation-authority.md.
    """

    standing: Standing
    reason: str | None = None
    intent: Intent
    pre_state: dict[str, object] | None = None
    post_state: dict[str, object] | None = None
