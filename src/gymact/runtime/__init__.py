"""Reference runtime enforcing zero-unreceipted-actuation.

See .claude/rules/actuation-authority.md. `ReferenceEnvironment` is a real, in-process
implementation (not a test double) used both directly and as the collaborator under
test in tests/test_runtime.py.
"""

from __future__ import annotations

from typing import Protocol

from gymact.model import ActuationResult, Capability, Consequence, Intent, Standing

__all__ = ["Environment", "ReferenceEnvironment"]


class Environment(Protocol):
    """A materialized world exposing capabilities for observation and actuation."""

    def observe(self, capability_id: str) -> dict[str, object]:
        """Read current state for a capability. Never requires authority."""
        ...

    def actuate(self, intent: Intent) -> ActuationResult:
        """Attempt a consequential state change. Enforces the authority invariant."""
        ...


class ReferenceEnvironment:
    """Minimal in-process Environment holding real, mutable capability state.

    Registered capabilities each own one piece of state (a dict). `actuate()` refuses
    any DO-consequence intent that lacks an `authority_ref`, and never mutates state
    on refusal.
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}
        self._state: dict[str, dict[str, object]] = {}

    def register(self, capability: Capability, initial_state: dict[str, object]) -> None:
        """Register a capability with its initial state."""
        self._capabilities[capability.id] = capability
        self._state[capability.id] = dict(initial_state)

    def observe(self, capability_id: str) -> dict[str, object]:
        """Return the current state for a capability. Read-only, no authority needed."""
        return dict(self._state[capability_id])

    def actuate(self, intent: Intent) -> ActuationResult:
        """Apply `intent.payload` to capability state if authorized, else refuse."""
        capability = self._capabilities[intent.capability_id]
        pre_state = dict(self._state[intent.capability_id])

        if capability.consequence is Consequence.DO and intent.authority_ref is None:
            return ActuationResult(
                standing=Standing.REFUSED,
                reason="DO capability requires authority_ref; none was provided.",
                intent=intent,
                pre_state=pre_state,
                post_state=None,
            )

        new_state = {**pre_state, **intent.payload}
        self._state[intent.capability_id] = new_state
        return ActuationResult(
            standing=Standing.ACCEPTED,
            intent=intent,
            pre_state=pre_state,
            post_state=dict(new_state),
        )
