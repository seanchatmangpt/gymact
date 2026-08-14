# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Generic structural-replay runner for a real
:class:`~gymact.powl.algebra.PowlNode` tree.

This module is deliberately pipeline-shape-agnostic: every label literal,
every SRE-diagnosing-pipeline-specific frozenset, and every Turtle/
``ChoiceGraph`` tree-construction helper that used to live here
(``PIPELINE_LINEAR_STEPS``, ``CASE_RETRIEVE_LABEL``/``CASE_HIT_LABEL``/
``CASE_MISS_LABEL``/``CASE_RETAIN_LABEL``/``RECORD_LABEL``, every
``GYMACT_*_LABEL`` constant, ``ALLOWED_ACTION_BINDING_LABELS`` /
``ALLOWED_ACTUATION_BINDING_LABELS`` / ``ALLOWED_ACTUATION_ORACLE_LABELS``,
``build_pipeline_turtle``, ``build_pipeline_powl_node``,
``_concurrent_read_block``) has moved to autofde-lab's own
``src/autofde_lab/fabric/gymact_pipeline.py`` -- the one real caller of this
runner with SRE-diagnosing-pipeline knowledge. That module constructs one
:class:`~gymact.powl.spec.PowlPipelineSpec` (``PIPELINE_SPEC``) carrying its
own label sets and calls :func:`run_pipeline` here with
``spec=PIPELINE_SPEC``.

Splitting the module this way removes gymact's dependency-direction
violation: this file has zero ``autofde_lab`` imports. ``gymact`` must not
import ``autofde_lab`` (the reverse is true -- autofde-lab depends on
``gymact`` as an editable sibling package), and no permanent binding to one
caller's pipeline shape belongs in a package this generic.

No silent hang
---------------
Termination of a (possibly cyclic) choice graph is structural, never a
wall-clock timeout -- see ``executor.py``'s module docstring and
``bounds.py``'s three counters (``max_activity_fires``, ``max_node_visits``,
``max_marking_states``). :func:`classify_pipeline_stall` surfaces
``executor.classify_stall()``'s result directly rather than adding a new
timeout layer of its own.

The runner stays structural-only by default; a caller opts a narrow slice
into gated actuation
---------------------------------------------------------------------------
:func:`run_pipeline` never invokes a cluster-mutating (or otherwise
world-effecting) actuator as an unconditional side effect of structural
marking advancement. What it does allow is exactly what a caller's own
:class:`~gymact.powl.spec.PowlPipelineSpec` declares:

- Labels in ``spec.readonly_labels`` may only ever bind a bare
  :data:`~gymact.powl.spec.ActionBinding` callable -- pure computation, real
  lookups, real oracle calls; never a
  :class:`~gymact.powl.spec.GatedCapabilityBinding`. This is the
  structural-only guarantee, enforced at runtime (``isinstance`` checks
  below), not merely by convention.
- Labels in ``spec.actuation_labels`` may bind a real, mutating actuation
  step, but *only* as a :class:`~gymact.powl.spec.GatedCapabilityBinding`,
  whose construction already proved the wrapped capability name was
  admitted by a real :class:`~gymact.powl.spec.CapabilityGateLike` --
  before any Atom fires, never invoked ungated.
- Labels in ``spec.oracle_labels`` are actuation-adjacent but never
  capability-gated (there may be no real ``Capability`` to gate against --
  e.g. a plain coroutine oracle poll) -- they take a bare
  :data:`~gymact.powl.spec.ActionBinding`, like ``readonly_labels``, but are
  not required by the default completeness check below.

Collapsing any of these into "structural marking advancement doubles as
world-effecting authority" would hand a property of the *plan* (marking
advancement) the authority that belongs only to a brokered, independently
authorized actuation call (a property of the *world*) -- the same class of
admission/evidence defect this repo's own standing rules exist to name.
Any real actuation a caller's binding performs must already have been
admitted through its own gate before it is ever wrapped and bound here.

``action_bindings`` completeness -- refuse-if-incomplete by default
--------------------------------------------------------------------
When a non-empty ``action_bindings`` is given, the default is to require it
to cover ``spec.readonly_labels | spec.actuation_labels`` exactly (never
``spec.oracle_labels`` -- those stay optional per their own docstring
above). An Atom whose label has no bound callable still fires structurally
(the marking advances -- this runner never re-derives a different
traversal), but no ``action_result`` is ever computed for it and no
``powl_action_binding_error`` can ever be raised for it either, because the
callable that would have produced either is simply absent. A caller who
thinks their pipeline "ran end-to-end" from a clean :func:`run_pipeline`
return could otherwise be silently wrong about which steps actually
executed real logic -- and this is strictly worse for an unbound
``actuation_labels`` member than for an unbound ``readonly_labels`` one,
since the former is the higher-stakes, capability-gated-actuation case.
:func:`run_pipeline` therefore raises
:class:`~gymact.powl.spec.ActuationBindingRefused`, naming every missing
label, before any Atom fires.

A caller with a legitimate partial-pipeline use case opts out explicitly
with ``allow_partial_bindings=True``. Passing ``action_bindings=None`` or
``{}`` (no bindings at all) is unaffected by this check -- a caller running
a purely structural replay with zero bound callables is unambiguous about
what it did, unlike a partial dict that could be mistaken for complete.

``recorder_factory`` -- injection seam, not part of the documented public
contract's normal use
--------------------------------------------------------------------
When omitted (the default for every real caller), :func:`run_pipeline`
constructs its own
:class:`~gymact.powl.ocel_bridge.GymactOcelSessionRecorder` via
``spec.default_session_id``/``spec.recorder_server_name``. A caller may pass
a zero-arg-beyond-``session_id`` callable returning any real object
satisfying :class:`~gymact.powl.spec.OcelRecorderLike` instead -- e.g. an
autofde-lab-side adapter wrapping the real
``autofde_lab.ocel.mcp_instrumentation.OcelSessionRecorder`` if a caller
wants that project's OCPQ-law-validated ``OcelLog`` shape instead of
gymact's raw OCEL2-JSON-dict shape, or a small, real subclass that also
records ``threading.get_ident()`` on every ``record()`` call for a test to
assert directly on the *real* recorder's own invocation-thread identity.
This is a real injection point, not a mock: the object returned still
genuinely performs ``record()``/``close()``, never a stand-in that fakes the
interaction.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from gymact.powl import ocel_bridge
from gymact.powl.algebra import Atom, NodeId, OrderEdge, PowlNode
from gymact.powl.bounds import DEFAULT_BOUND, ExecutionBound
from gymact.powl.executor import (
    INITIAL_MARKING,
    Marking,
    NodePath,
    classify_stall,
    enabled,
    fire,
    is_final,
    node_at,
)
from gymact.powl.refusals import PowlError
from gymact.powl.spec import (
    ActionBinding,
    ActuationBindingRefused,
    BridgeUnavailable,
    GatedCapabilityBinding,
    OcelRecorderLike,
    PowlPipelineSpec,
)
from gymact.powl.validate import validate_model

__all__ = [
    "PipelineStallResult",
    "classify_pipeline_stall",
    "run_pipeline",
    # Re-exported for backward-compatible import sites -- now defined in
    # gymact.powl.spec, not this module.
    "ActionBinding",
    "ActuationBindingRefused",
    "BridgeUnavailable",
    "GatedCapabilityBinding",
    "OcelRecorderLike",
    "PowlPipelineSpec",
]


def _sequence(nodes: tuple[PowlNode, ...], *, start_index: int) -> frozenset[OrderEdge]:
    """The `OrderEdge` set chaining every adjacent pair in `nodes` (`nodes[i]
    -> nodes[i+1]` for each `i`), offset so `nodes[0]` sits at `start_index`
    in the caller's own top-level children tuple.

    Real, index-based counterpart to the real reference `powl` package's own
    `builders.py::sequence()` (`~/POWL/powl/objects/tagged_powl/builders.py`
    -- confirmed via direct read this session: `PartialOrder(nodes=ordered,
    edges=[(ordered[i], ordered[i+1]) for i in range(len(ordered)-1)], ...)`,
    an *object-identity*-keyed edge scheme). autofde-lab's own `algebra.py`
    addresses children by 0-based `NodeId` position instead (a deliberate,
    documented arena convention, mirroring `~/wasm4pm-compat/src/powl.rs` --
    kept as-is, not changed to match the reference), so this helper is the
    generic, index-based version of the same "chain every adjacent pair"
    pattern a caller building a linear pipeline tree needs -- kept here
    since it is generic tree-construction plumbing, not SRE-pipeline-shape
    knowledge."""
    return frozenset(
        OrderEdge(NodeId(start_index + i), NodeId(start_index + i + 1))
        for i in range(len(nodes) - 1)
    )


@dataclass(frozen=True, slots=True)
class PipelineStallResult:
    """What `classify_pipeline_stall` surfaces -- never a new timeout layer."""

    final: bool
    stall: str | None  # an `executor.DeadlockKind` value, or None if final/live


def classify_pipeline_stall(
    model: PowlNode,
    marking: Marking,
    bound: ExecutionBound = DEFAULT_BOUND,
) -> PipelineStallResult:
    """Surface `executor.classify_stall()` directly -- no wall-clock timeout.

    Per `executor.py`/`bounds.py`: termination is structural (three counters
    only), never a timeout. This function adds no bound of its own; it is a
    thin, honest pass-through so a caller of this runner gets the same
    `BLOCKED:BOUND_EXHAUSTED` / `BLOCKED:DEADLOCK` classification the
    executor already computes, rather than a silent hang.
    """
    if is_final(model, marking):
        return PipelineStallResult(final=True, stall=None)
    # `max_marking_states` is a genuine third gate here, alongside `fires`
    # and `not enabled(...)` -- found and fixed forward this session
    # (tests/powl/test_runner_bounds_concurrent_chicago.py`): unlike
    # `max_node_visits`, a `max_marking_states` exhaustion is invisible to
    # `enabled()` (it is enforced only inside `fire()`, never removes a
    # path from the enabled set), so a marking that `run_pipeline` actually
    # stopped advancing because of it can still have a real, structurally
    # enabled successor -- `enabled(...)` returns non-empty, and without
    # this explicit check this function fell through to the final `return
    # ... stall=None` line below ("more work enabled, not stalled"), which
    # is a genuinely honest-sounding but wrong verdict: the caller's own
    # `run_pipeline` loop had already halted, so "not stalled" mis-reported
    # a real stop as ongoing progress.
    if (
        marking.fires >= bound.max_activity_fires
        or len(marking.completed_paths) >= bound.max_marking_states
        or not enabled(model, marking, bound)
    ):
        # Delegate the actual verdict to executor.classify_stall itself --
        # this module never re-derives BOUND_EXHAUSTED vs. DEADLOCK on its
        # own, only forwards the executor's real classification.
        return PipelineStallResult(final=False, stall=str(classify_stall(model, marking, bound)))
    return PipelineStallResult(final=False, stall=None)  # more work enabled, not stalled


def run_pipeline(
    model: PowlNode,
    *,
    spec: PowlPipelineSpec,
    session_id: str | None = None,
    action_bindings: dict[str, ActionBinding | GatedCapabilityBinding] | None = None,
    bound: ExecutionBound = DEFAULT_BOUND,
    allow_partial_bindings: bool = False,
    recorder_factory: Callable[[str], OcelRecorderLike] | None = None,
) -> tuple[dict[str, Any], PipelineStallResult]:
    """Drive `model` to completion or to a classified stall, recording one
    real `"powl_structural_fire"` OCEL event per fire, while retaining the
    `Marking` so a caller gets `classify_pipeline_stall`'s real verdict
    instead of a silently-incomplete log.

    `spec` is required and keyword-only: every caller must be explicit about
    its own allowed labels (`spec.readonly_labels` /
    `spec.actuation_labels` / `spec.oracle_labels`), preserving the
    "never silently permissive" refusal discipline this runner has always
    had rather than defaulting to an empty/unbounded set. See this module's
    docstring for the full label-set / gating contract `spec` carries.

    Enforces that contract at runtime, not merely in prose: any
    `action_bindings` key outside the union of `spec`'s three label sets
    raises `ActuationBindingRefused` before any Atom fires -- a caller
    cannot wire a cluster-mutating actuator to fire as a side effect of
    structural marking advancement.

    Admission is mandatory, not optional: `validate_model(model)` is called
    unconditionally, before doing anything else -- mirroring
    `guard_executor.execute()`'s own "before doing anything else, every
    time" discipline (see that module's docstring) at this runner's own
    entry point. A model that has not itself been independently
    re-validated here is never walked or fired, even if a caller claims it
    was already checked elsewhere; per-fire `atom_attrs` (built from
    `node.action`/`node.bindings` below) are only ever derived from a model
    that has passed this structural check first.
    """
    validate_model(model)

    if action_bindings:
        known_labels = spec.readonly_labels | spec.actuation_labels | spec.oracle_labels
        refused = sorted(set(action_bindings) - known_labels)
        if refused:
            raise ActuationBindingRefused(
                f"run_pipeline refuses action_bindings for label(s) {refused!r} -- "
                f"only {sorted(known_labels)!r} (read-only/diagnostic pipeline steps, "
                f"plus the narrow, capability-gated actuation-class labels in "
                f"spec.actuation_labels) may be bound. Any other real actuation step "
                f"must be reached through a separate, explicitly authorized call "
                f"outside this replay."
            )

        ungated = sorted(
            label
            for label in action_bindings
            if label in spec.actuation_labels
            and not isinstance(action_bindings[label], GatedCapabilityBinding)
        )
        if ungated:
            raise ActuationBindingRefused(
                f"REFUSED:UNGATED_ACTUATION_BINDING label(s)={ungated!r} -- an "
                f"actuation-class label may only be bound to a real "
                f"GatedCapabilityBinding (whose construction already proved the "
                f"wrapped capability name was admitted by a real CapabilityGateLike), "
                f"never a bare ActionBinding callable. Wrap the callable in "
                f"GatedCapabilityBinding(capability_name=..., callable_=..., gate=...) "
                f"before binding it to {ungated!r}."
            )

        misgated = sorted(
            label
            for label in action_bindings
            if label in (spec.readonly_labels | spec.oracle_labels)
            and isinstance(action_bindings[label], GatedCapabilityBinding)
        )
        if misgated:
            raise ActuationBindingRefused(
                f"REFUSED:ACTUATION_BINDING_ON_READONLY_LABEL label(s)={misgated!r} -- "
                f"spec.readonly_labels and spec.oracle_labels may only ever take a "
                f"bare ActionBinding callable, never a GatedCapabilityBinding (or any "
                f"other capability-gated actuation wrapper). Their structural-only "
                f"guarantee stays unconditional."
            )

        if not allow_partial_bindings:
            # Covers spec.readonly_labels AND spec.actuation_labels -- an
            # actuation-class label with no bound callable at all is exactly
            # the silent-no-op risk this check exists to catch, and it is
            # the higher-stakes case (a real, capability-gated actuation
            # step silently never firing), not a narrower one than
            # readonly_labels. spec.oracle_labels stays excluded, per its
            # own docstring above ("never required by the default
            # bindings-completeness check").
            required_labels = spec.readonly_labels | spec.actuation_labels
            missing = sorted(required_labels - set(action_bindings))
            if missing:
                raise ActuationBindingRefused(
                    f"run_pipeline refuses incomplete action_bindings -- missing "
                    f"binding(s) for label(s) {missing!r}. An unbound label still "
                    f"fires structurally but silently skips its action_result / "
                    f"binding-error reporting, which could let a caller believe "
                    f"their pipeline ran end-to-end when a step was actually a "
                    f"no-op. Pass a callable for every label in "
                    f"{sorted(required_labels)!r}, or pass "
                    f"allow_partial_bindings=True to explicitly opt into a "
                    f"partial pipeline."
                )

    session_id = session_id or spec.default_session_id
    recorder = (
        recorder_factory(session_id)
        if recorder_factory is not None
        else ocel_bridge.GymactOcelSessionRecorder(
            session_id, server_name=spec.recorder_server_name
        )
    )

    marking: Marking = INITIAL_MARKING
    step = 0
    while not is_final(model, marking):
        if marking.fires >= bound.max_activity_fires:
            # `fire()` itself raises BOUND_EXHAUSTED past this point; checked
            # here instead so a fire-budget stall stops the loop the same
            # honest, non-raising way a visit-cap or deadlock stall does --
            # `classify_pipeline_stall` below reports which one it was.
            break
        live = enabled(model, marking, bound)
        if not live:
            break
        batch: list[NodePath] = sorted(live)  # deterministic ORDER; never a subset pick

        if len(batch) == 1:
            # Byte-identical to the pre-existing single-path body, except for
            # the try/except immediately below -- keeps every pre-existing
            # test passing unchanged (the try/except is a no-op whenever
            # `fire()` does not raise).
            chosen: NodePath = batch[0]
            node = node_at(model, chosen)
            label = node.label if isinstance(node, Atom) else f"path:{chosen}"

            # Genuine bug found and fixed forward this session (tests/powl/
            # test_runner_bounds_concurrent_chicago.py): the top-of-loop
            # `if marking.fires >= bound.max_activity_fires: break` only
            # guards the fire-budget bound. `max_marking_states` (bounds.py)
            # is enforced *inside* `fire()` itself and was left uncaught
            # here, unlike the concurrent batch path's Step A (`except
            # PowlError: break` below) -- so a `max_marking_states`
            # exhaustion discovered on the single-fire path (concretely:
            # right after a concurrent batch partially fired and left
            # exactly one path enabled) propagated out of `run_pipeline` as
            # an uncaught `PowlError` instead of the honest, classified
            # `BLOCKED:BOUND_EXHAUSTED` stall every other bound-exhaustion
            # path already returns. Mirrors Step A's own handling exactly:
            # stop advancing, let `classify_pipeline_stall` report the real
            # verdict afterward.
            try:
                marking = fire(model, marking, chosen, bound=bound)
            except PowlError:
                break
            step += 1

            node_object_id = f"{session_id}-node-{'.'.join(map(str, chosen))}"
            outcome: dict[str, Any] = {"standing": "FIRED", "detail": label, "steps_taken": step}

            binding = action_bindings.get(label) if action_bindings else None
            if binding is not None and isinstance(node, Atom):
                atom_attrs = {"label": node.label, "action": node.action, "bindings": dict(node.bindings)}
                try:
                    outcome["action_result"] = binding(atom_attrs)
                except Exception as exc:  # noqa: BLE001 -- recorded honestly, then re-raised
                    recorder.record(
                        activity="powl_action_binding_error",
                        objects=[(node_object_id, "PowlNode")],
                        outcome={
                            "standing": "ERROR",
                            "detail": label,
                            "steps_taken": step,
                            "error": f"{type(exc).__name__}: {exc}",
                        },
                    )
                    raise

            recorder.record(
                activity="powl_structural_fire",
                objects=[(node_object_id, "PowlNode")],
                outcome=outcome,
            )
            continue

        # len(batch) > 1: real concurrent batch-fire -- the executor's own
        # documented law ("the caller picks... never a tie-break") applied
        # for real: fire the whole concurrently-enabled set, not one
        # arbitrarily chosen member.
        #
        # Step A: advance the marking for every chosen path first,
        # sequentially, on the calling thread -- `fire()` is pure/cheap
        # (frozen `Marking`, `dataclasses.replace`, no module-level state),
        # so doing all fires up front keeps `marking` fully consistent before
        # any binding (slow, impure, may raise) runs. Handle BOUND_EXHAUSTED
        # honestly mid-batch: if `fire()` raises partway through, stop firing
        # further batch members; only what actually fired gets a binding
        # invoked or an event recorded, and `classify_pipeline_stall` reports
        # the real verdict afterward.
        fired_this_round: list[tuple[NodePath, PowlNode, str, int]] = []
        for path in batch:
            try:
                marking = fire(model, marking, path, bound=bound)
            except PowlError:
                break  # BOUND_EXHAUSTED mid-batch -- stop firing; handle what did fire below
            step += 1
            fired_node = node_at(model, path)
            fired_label = fired_node.label if isinstance(fired_node, Atom) else f"path:{path}"
            fired_this_round.append((path, fired_node, fired_label, step))

        if not fired_this_round:
            # Genuine bug found and fixed forward this session (tests/powl/
            # test_runner_bounds_concurrent_chicago.py): a >1-sized batch
            # whose very FIRST fire attempt already raises `PowlError`
            # (e.g. a second concurrent batch, recomputed fresh at the top
            # of the loop, whose first member is already over budget
            # because an earlier round spent the whole bound) leaves
            # `marking` completely unchanged by this iteration. Without
            # this explicit `break`, the `while not is_final(...)` loop
            # would recompute the exact same non-empty `batch` next
            # iteration (nothing advanced) and retry the exact same failing
            # first fire forever -- a genuine hang, not merely the
            # `ThreadPoolExecutor(max_workers=0)` crash this guard was
            # originally added alongside (see Step B's own comment). Every
            # other honest stop in this loop (the `max_activity_fires`
            # pre-check above, Step A's own partial-batch `break`, `not
            # live: break`) already leaves the loop via a path that either
            # advanced `marking` or exits outright -- this is the one gap
            # where neither happened.
            break

        # Step B: invoke bindings for everything that DID fire, concurrently,
        # via a ThreadPoolExecutor sized to the batch -- every future starts
        # immediately, so there is never a queued-but-not-started future to
        # cancel on error.
        #
        # Genuine bug found and fixed forward this session (tests/powl/
        # test_runner_bounds_concurrent_chicago.py): `fired_this_round` can
        # legitimately be EMPTY -- not just partially filled -- whenever a
        # bound is exhausted on the very *first* fire attempt of a >1-sized
        # batch (concretely: a second concurrent batch, computed fresh at
        # the top of the loop, whose first member is already over budget
        # because an earlier round used up the whole bound). Constructing
        # `ThreadPoolExecutor(max_workers=len(fired_this_round))` with that
        # count `== 0` raised `ValueError("max_workers must be greater than
        # 0")` uncaught -- a crash on an entirely legitimate, honest "0 of a
        # >1 batch fired" outcome. Step C's own loop below was already a
        # correct no-op over an empty `fired_this_round`; only Step B needed
        # this guard.
        results: dict[NodePath, Any] = {}
        errors: dict[NodePath, Exception] = {}
        if fired_this_round:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(fired_this_round)) as pool:
                future_to_path: dict[concurrent.futures.Future, NodePath] = {}
                for path, fired_node, fired_label, _fired_step in fired_this_round:
                    binding = action_bindings.get(fired_label) if action_bindings else None
                    if binding is not None and isinstance(fired_node, Atom):
                        atom_attrs = {
                            "label": fired_node.label,
                            "action": fired_node.action,
                            "bindings": dict(fired_node.bindings),
                        }
                        future_to_path[pool.submit(binding, atom_attrs)] = path
                for future in concurrent.futures.as_completed(future_to_path):
                    path = future_to_path[future]
                    try:
                        results[path] = future.result()
                    except Exception as exc:  # noqa: BLE001 -- recorded honestly, then re-raised
                        errors[path] = exc

        # Step C: record OCEL events sequentially on the calling thread
        # (the recorder is not thread-safe -- single-writer -- so recording
        # must never happen from a worker thread), in batch order, for every
        # fired path, success or error, THEN raise the first error in that
        # same deterministic order if any.
        for path, fired_node, fired_label, fired_step in fired_this_round:
            node_object_id = f"{session_id}-node-{'.'.join(map(str, path))}"
            if path in errors:
                exc = errors[path]
                recorder.record(
                    activity="powl_action_binding_error",
                    objects=[(node_object_id, "PowlNode")],
                    outcome={
                        "standing": "ERROR",
                        "detail": fired_label,
                        "steps_taken": fired_step,
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
                continue
            outcome = {"standing": "FIRED", "detail": fired_label, "steps_taken": fired_step}
            if path in results:
                outcome["action_result"] = results[path]
            recorder.record(
                activity="powl_structural_fire",
                objects=[(node_object_id, "PowlNode")],
                outcome=outcome,
            )
        if errors:
            first_path = next(p for p, *_ in fired_this_round if p in errors)
            raise errors[first_path]

    return recorder.close(), classify_pipeline_stall(model, marking, bound)
