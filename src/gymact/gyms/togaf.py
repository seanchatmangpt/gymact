"""Minimal, real TOGAF Preliminary + Requirements Management gym.

This is the v26.8.11 M1 vertical slice from
`docs/prd/v26.8.11-togaf-fortune5-adm-gym.md`: the smallest real, actuatable
proof that a TOGAF ADM lifecycle can be materialized/observed/actuated/
verified through GymAct's real kernel, authority-gated, with independent
verification and OCEL evidence -- deliberately smaller than the PRD's full
M1 description (two ADM phases only, no SHACL verifier, no ODRL governance
gating, no synthetic Fortune-5 data generator; those are named PRD scope for
M2-M4, not this pass).

State is a fact set, the same pattern `gymact.gyms.opaque_procedure` already
uses, naming the same requirement subjects already declared in
`ggen/togaf-gym-pack/ontology.ttl` (`urn:gymact:togaf:req:continuity`,
`:residency`, `:latency`, `:cost`) so a future PRD milestone that extends the
ontology with real `sosa:Procedure` capability facts for these two
capabilities has a matching Python-side name to project from.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

REQUIREMENT_SUBJECTS: tuple[str, ...] = ("continuity", "residency", "latency", "cost")

CAPABILITY_INSPECT = "urn:gymact:togaf:capability:inspect-requirements-traceability"
CAPABILITY_ESTABLISH = "urn:gymact:togaf:capability:establish-architecture-capability"
CAPABILITY_SUBMIT = "urn:gymact:togaf:capability:submit-requirement"

_CAPABILITY_FACT = "capability:architecture-established"


def _requirement_fact(requirement: str) -> str:
    return f"requirement:{requirement}:submitted"


class TogafEnvironment:
    """Preliminary phase (establish capability) + Requirements Management
    phase (submit the four already-admitted requirement subjects), as a real
    fact-set world."""

    def __init__(self, *, requires_authority: bool) -> None:
        self.environment_id = f"urn:gymact:togaf:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._state: set[str] = set()
        self._closed = False
        self._capabilities = (
            Capability(
                iri=CAPABILITY_INSPECT,
                title="Inspect requirements traceability",
                consequence=Consequence.READ,
                binding=CAPABILITY_INSPECT,
            ),
            Capability(
                iri=CAPABILITY_ESTABLISH,
                title="Establish architecture capability",
                consequence=Consequence.DO,
                binding=CAPABILITY_ESTABLISH,
            ),
            Capability(
                iri=CAPABILITY_SUBMIT,
                title="Submit requirement",
                consequence=Consequence.DO,
                binding=CAPABILITY_SUBMIT,
            ),
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def _goal_facts(self) -> frozenset[str]:
        return frozenset(
            {_CAPABILITY_FACT, *(_requirement_fact(r) for r in REQUIREMENT_SUBJECTS)}
        )

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return self._capabilities

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return {
            "facts": sorted(self._state),
            "goal_reached": self._goal_facts() <= self._state,
        }

    async def actuate(
        self, capability: Capability, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self._ensure_open()
        if capability.binding == CAPABILITY_ESTABLISH:
            if payload:
                raise ValueError("ESTABLISH_ACCEPTS_NO_PAYLOAD")
            if _CAPABILITY_FACT in self._state:
                raise ValueError("ALREADY_ESTABLISHED_REFUSED")
            before = sorted(self._state)
            self._state.add(_CAPABILITY_FACT)
            return {
                "action": capability.binding,
                "before_facts": before,
                "after_facts": sorted(self._state),
            }
        if capability.binding == CAPABILITY_SUBMIT:
            requirement = payload.get("requirement") if isinstance(payload, dict) else None
            if requirement not in REQUIREMENT_SUBJECTS:
                raise ValueError(f"UNKNOWN_REQUIREMENT:{requirement!r}")
            if _CAPABILITY_FACT not in self._state:
                raise ValueError("PRECONDITION_REFUSED:CAPABILITY_NOT_ESTABLISHED")
            fact = _requirement_fact(requirement)
            if fact in self._state:
                raise ValueError("ALREADY_SATISFIED_REFUSED")
            before = sorted(self._state)
            self._state.add(fact)
            return {
                "action": capability.binding,
                "requirement": requirement,
                "before_facts": before,
                "after_facts": sorted(self._state),
            }
        raise ValueError("UNKNOWN_TOGAF_ACTION")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        allowed = {"goal_reached"}
        unknown = set(expected) - allowed
        if unknown:
            raise ValueError(f"UNSUPPORTED_TOGAF_VERIFICATION:{sorted(unknown)!r}")
        passed = True
        if "goal_reached" in expected:
            if not isinstance(expected["goal_reached"], bool):
                raise TypeError("expected.goal_reached must be a boolean")
            passed = observed["goal_reached"] is expected["goal_reached"]
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {"facts": sorted(self._state)}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        facts = checkpoint.get("facts")
        if not isinstance(facts, list) or not all(isinstance(item, str) for item in facts):
            raise TypeError("checkpoint.facts must be a list of strings")
        self._state = set(facts)

    async def teardown(self) -> None:
        self._closed = True


class TogafProvider:
    """Materialize a fresh TOGAF Preliminary/Requirements Management episode."""

    name = "togaf"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> TogafEnvironment:
        del scenario
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return TogafEnvironment(requires_authority=requires_authority)
