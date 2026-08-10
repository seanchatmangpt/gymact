"""Named, narrower Protocol views over `gymact.providers.Environment`.

This module adds no behavior and duplicates no logic. `Environment`
(`gymact/providers.py`) stays the real, working implementation surface --
this module only gives three of its existing methods explicit names that
match the gym algebra's OBSERVE/DO/VERIFY split:

    Environment.capabilities/observe  -> Observer
    Environment.actuate               -> Actuator
    Environment.verify                -> Verifier

Because these are `typing.Protocol` classes with identical method
signatures to the corresponding subset of `Environment`, Python's
structural typing means every existing `Environment` implementation
(`MemoryEnvironment`, `GymnasiumEnvironment`, `KubernetesReconciliationEnvironment`,
...) already satisfies `Observer`, `Actuator`, and `Verifier` with zero
adapter code -- see `tests/test_algebra_protocols.py` for a real,
non-mocked `isinstance` proof against real materialized environments.

GymAct owns OBSERVE/DO/VERIFY only (not SELECT/CONSTRUCT, which belong to
callers composing plans on top of these operations) -- see
`docs/2026-08-08-gymact-constitution.md` for the full gym algebra mapping.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from gymact.models import Capability


@runtime_checkable
class Observer(Protocol):
    """The OBSERVE half of the gym algebra: read a bounded world's current
    state and the capabilities available on it, with no side effect.

    Structurally identical to `Environment.capabilities`/`Environment.observe`
    -- any `Environment` already satisfies this Protocol."""

    def capabilities(self) -> tuple[Capability, ...]: ...

    async def observe(self) -> dict[str, Any]: ...


@runtime_checkable
class Actuator(Protocol):
    """The DO half of the gym algebra: apply one `Capability` with a payload,
    producing a real consequence in the bounded world.

    Structurally identical to `Environment.actuate` -- any `Environment`
    already satisfies this Protocol."""

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class Verifier(Protocol):
    """The VERIFY half of the gym algebra: independently check observed state
    against an expected shape, distinct from the actuator's own success report.

    Structurally identical to `Environment.verify` -- any `Environment`
    already satisfies this Protocol."""

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]: ...
