# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Generic pipeline-shape contract for :mod:`gymact.powl.runner`.

``gymact.powl`` must not import ``autofde_lab`` -- the dependency direction
is the reverse (autofde-lab depends on gymact as an editable sibling
package). This module carries the types ``runner.py`` previously reached
into ``autofde_lab.fabric.gymact_capability_gate`` /
``autofde_lab.ocel.powl_replay`` / ``autofde_lab.ocel.mcp_instrumentation``
for, expressed as local, self-contained types (a frozen configuration
dataclass and two structural ``Protocol``s) instead.

No label literals live here. Every SRE-pipeline-specific label constant
(``PIPELINE_LINEAR_STEPS``, the ``GYMACT_*_LABEL`` names, the three
``ALLOWED_*_LABELS`` frozensets) belongs to the caller that owns that
domain-specific pipeline shape -- e.g. autofde-lab's own
``fabric/gymact_pipeline.py`` -- which constructs one :class:`PowlPipelineSpec`
from its own label sets and passes it to :func:`gymact.powl.runner.run_pipeline`
as a required, keyword-only argument. This keeps ``run_pipeline`` itself
generic: it enforces the *shape* of the refusal discipline (unknown label ->
refused; actuation-class label requires a real gated binding; incomplete
bindings refused unless opted out) without hard-coding *which* labels count
as which class.

``CapabilityGateLike``/``OcelRecorderLike`` are structural (``@runtime_checkable``)
Protocols, not abstract base classes a caller must subclass from. A real,
concrete ``autofde_lab.fabric.gymact_capability_gate.CapabilityGate`` already
has exactly the one method ``CapabilityGateLike`` declares
(``check(self, binding: str) -> None``) and satisfies this Protocol
structurally with zero edits on its side; a gymact-native caller with no
TOML manifest at all can satisfy the same Protocol with a trivial local
class. Likewise, :class:`~gymact.powl.ocel_bridge.GymactOcelSessionRecorder`
satisfies ``OcelRecorderLike`` structurally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Protocol, runtime_checkable

#: One `Atom.bindings`-shaped payload in, any real result out. Local
#: replacement for the 1-line alias previously imported from
#: `autofde_lab.ocel.powl_replay.ActionBinding` -- same shape, no import.
ActionBinding = Callable[[dict[str, Any]], Any]

__all__ = [
    "ActionBinding",
    "CapabilityGateLike",
    "OcelRecorderLike",
    "PowlPipelineSpec",
    "ActuationBindingRefused",
    "BridgeUnavailable",
    "GatedCapabilityBinding",
]


@runtime_checkable
class CapabilityGateLike(Protocol):
    """Structural contract for whatever gate `GatedCapabilityBinding` wraps.

    A real `CapabilityGate.check(binding)` raises a named, typed error
    (`CapabilityRefused`) when `binding` is not in its loaded allowlist, and
    returns `None` silently when it is. This Protocol asserts only the
    shape, never the concrete exception type -- `gymact.powl` has no
    dependency on whatever error vocabulary a caller's gate raises.
    """

    def check(self, binding: str) -> None: ...


@runtime_checkable
class OcelRecorderLike(Protocol):
    """Structural contract for `run_pipeline`'s OCEL recorder seam.

    Satisfied by :class:`~gymact.powl.ocel_bridge.GymactOcelSessionRecorder`
    (the default), or by any real recorder a caller supplies via
    `recorder_factory` -- e.g. a thin adapter wrapping
    `autofde_lab.ocel.mcp_instrumentation.OcelSessionRecorder` at the
    autofde-lab call site, outside `gymact.powl` entirely.
    """

    def record(
        self, *, activity: str, objects: Iterable[tuple[str, str]], outcome: Mapping[str, Any]
    ) -> None: ...

    def close(self) -> Any: ...


@dataclass(frozen=True, slots=True)
class PowlPipelineSpec:
    """The label-set configuration `run_pipeline` needs but never owns.

    A caller constructs one instance from its own domain-specific label
    sets (see e.g. autofde-lab's `fabric/gymact_pipeline.py`) and passes it
    to `run_pipeline(model, spec=..., ...)`. Required, keyword-only, no
    default -- every caller must be explicit about its own allowed labels,
    preserving `run_pipeline`'s original "never silently permissive"
    refusal discipline instead of defaulting to an empty/unbounded set.
    """

    #: Labels that may only ever take a bare `ActionBinding` callable --
    #: `run_pipeline` refuses a `GatedCapabilityBinding` bound to any of
    #: these (`REFUSED:ACTUATION_BINDING_ON_READONLY_LABEL`).
    readonly_labels: frozenset[str]
    #: Labels that may only ever take a real `GatedCapabilityBinding` --
    #: `run_pipeline` refuses a bare callable bound to any of these
    #: (`REFUSED:UNGATED_ACTUATION_BINDING`).
    actuation_labels: frozenset[str] = frozenset()
    #: Actuation-adjacent labels with no real capability to gate against
    #: (e.g. a plain oracle coroutine) -- take a bare `ActionBinding`, same
    #: as `readonly_labels`, but are never required by the default
    #: bindings-completeness check the way `readonly_labels` are.
    oracle_labels: frozenset[str] = frozenset()
    default_session_id: str = "powl-pipeline"
    recorder_server_name: str = "powl-runner"


class ActuationBindingRefused(ValueError):
    """Raised when `run_pipeline` is given an `action_bindings` key outside
    `spec.readonly_labels` / `spec.actuation_labels` / `spec.oracle_labels`
    -- i.e. a caller trying to wire a binding to fire as a side effect of
    structural marking advancement outside the label classes its own `spec`
    declared. Also raised when: (a) `action_bindings` is incomplete relative
    to `spec.readonly_labels` and the caller did not explicitly opt into a
    partial pipeline via `allow_partial_bindings`; or (b) an actuation-class
    label (`spec.actuation_labels`) is bound to anything other than a real
    `GatedCapabilityBinding`; or (c) a read-only/oracle label is bound to a
    `GatedCapabilityBinding` -- those labels may only ever take a bare
    `ActionBinding`, keeping their structural-only guarantee unconditional.
    """


class BridgeUnavailable(ValueError):
    """Raised when a caller's own tree-building helper (e.g. a
    `turtle_bridge`-backed pipeline constructor) did not produce the shape
    `run_pipeline`'s caller needs. `gymact.powl.runner` itself never raises
    this -- it is here as a shared, importable error type so callers don't
    each define their own."""


@dataclass(frozen=True, slots=True)
class GatedCapabilityBinding:
    """The only construction path an actuation-class Atom label
    (`spec.actuation_labels`) may bind to.

    Wraps a raw `ActionBinding` callable together with the real capability
    name it exercises, and proves that name is admitted by a real
    `CapabilityGateLike` gate both at *wrap time* -- `__post_init__` calls
    `gate.check(capability_name)` immediately, so an unauthorized capability
    can never even be constructed as a binding -- and again on *every single
    invocation* via `__call__`, which repeats the same `gate.check(...)`
    call before delegating to the wrapped callable.

    The construction-time check alone is not sufficient: this object is a
    frozen, slotted dataclass, so a single instance is long-lived and
    routinely reused across many fires -- e.g. a caller's `action_bindings`
    dict is built once and then invoked once per fire of the label inside a
    cyclic `ChoiceGraph` loop (POWL 2.0's designed iteration mechanism), or
    once per task in a concurrent batch, or across multiple `run_pipeline`
    calls that share one long-lived binding. If the underlying gate's
    allowlist is mutable and the capability is revoked mid-run, only a
    per-call re-check can catch that revocation before the next fire; a
    check that ran once at construction cannot. Re-checking on every call
    raises whatever named, typed error the caller's own gate defines (e.g.
    `CapabilityRefused` from `autofde_lab.fabric.gymact_capability_gate`) at
    the moment authorization is actually withdrawn, not merely at the
    moment the wrapper object happened to be built.

    `gate` is typed against the structural `CapabilityGateLike` Protocol
    (not a concrete class), so a real `autofde_lab.fabric.gymact_capability_gate.CapabilityGate`
    -- which already has exactly this `check(binding: str) -> None` method
    signature -- satisfies it with zero edits on its side.
    """

    capability_name: str
    callable_: ActionBinding
    gate: CapabilityGateLike

    def __post_init__(self) -> None:
        self.gate.check(self.capability_name)

    def __call__(self, atom_attrs: dict[str, Any]) -> Any:
        self.gate.check(self.capability_name)
        return self.callable_(atom_attrs)
