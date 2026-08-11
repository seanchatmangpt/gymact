"""Algebraic laws for DCM possibility paths, plus named Protocol views over
`gymact.providers.Environment`.

This module holds two independent, real pieces of content that both landed
here under this module's name:

1. `identity_path`/`compose_paths`/`zero_objectives` -- algebraic laws for
   composing `PossibilityPath`s (from `gymact.combinatorial`), depended on
   by `gymact.dcm`'s public facade and `tests/test_combinatorial_algebra.py`.

2. `Observer`/`Actuator`/`Verifier` -- narrower `typing.Protocol` views over
   `Environment`'s existing methods (`gymact/providers.py` stays the real,
   working implementation surface; this adds no behavior and duplicates no
   logic):

       Environment.capabilities/observe  -> Observer
       Environment.actuate               -> Actuator
       Environment.verify                -> Verifier

   Because these are `typing.Protocol` classes with identical method
   signatures to the corresponding subset of `Environment`, Python's
   structural typing means every existing `Environment` implementation
   (`MemoryEnvironment`, `GymnasiumEnvironment`,
   `KubernetesReconciliationEnvironment`, ...) already satisfies `Observer`,
   `Actuator`, and `Verifier` with zero adapter code -- see
   `tests/test_algebra_protocols.py` for a real, non-mocked `isinstance`
   proof against real materialized environments.

   GymAct owns OBSERVE/DO/VERIFY only (not SELECT/CONSTRUCT, which belong to
   callers composing plans on top of these operations) -- see
   `docs/2026-08-08-gymact-constitution.md` for the full gym algebra mapping.

A prior commit (`6e46cb2`, nominally an unrelated sregym subprocess-env fix)
accidentally overwrote this file's DCM content with only the Protocol
classes; both pieces are real and intentional (see `4ec5233` and `6e46cb2`
respectively), so this file keeps both rather than picking a winner.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from gymact.combinatorial import ObjectiveVector, PossibilityPath
from gymact.models import Capability


def identity_path(object_id: str) -> PossibilityPath:
    """Identity morphism represented by a zero-edge path at one object."""
    if not object_id:
        raise ValueError("IDENTITY_PATH_REQUIRES_OBJECT")
    return PossibilityPath(object_ids=(object_id,))


def compose_paths(left: PossibilityPath, right: PossibilityPath) -> PossibilityPath:
    """Compose adjacent paths; non-adjacent composition is mechanically refused."""
    if not left.object_ids or not right.object_ids:
        raise ValueError("PATH_COMPOSITION_REQUIRES_OBJECTS")
    if left.object_ids[-1] != right.object_ids[0]:
        raise ValueError("PATH_COMPOSITION_ENDPOINT_MISMATCH")
    return PossibilityPath(
        object_ids=(*left.object_ids, *right.object_ids[1:]),
        morphism_ids=(*left.morphism_ids, *right.morphism_ids),
        objectives=left.objectives.compose(right.objectives),
    )


def zero_objectives() -> ObjectiveVector:
    """Neutral objective element for identity-path composition."""
    return ObjectiveVector()


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
