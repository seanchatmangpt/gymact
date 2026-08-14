# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""A real, fully featured executor for admitted POWL 2.0 models.

Walks a :class:`~gymact.powl.algebra.PowlNode` tree, executing
:class:`~gymact.powl.algebra.Atom` leaves via a caller-supplied
``atom_invoker`` and choosing :class:`~gymact.powl.algebra.ChoiceGraph`
transitions via a caller-supplied, deterministic ``guard_evaluator`` -- never
an LLM call, never a second, competing decision mechanism.

Admission is mandatory, not optional
-------------------------------------
:func:`execute` calls :func:`gymact.powl.validate.validate_model` on the
top-level node before doing anything else, every time -- including on
resume (:attr:`resume_from`). A model this executor has not itself
independently re-validated is never walked, even if the caller claims it was
already checked elsewhere -- this mirrors ``validate.py``'s own
anti-self-attestation discipline, applied at the one remaining seam (a
caller skipping validation) that module cannot close by itself.

DSPy reasons, GymAct actuates -- unchanged by this module
-------------------------------------------------------------
This executor invokes an ``Atom``'s bound real callable via
``atom_invoker(atom)`` (or ``atom_invoker(atom, context)`` when a
:class:`ExecutionContext` is supplied) and nothing else. For a
``consequence="DO"`` atom, ``atom_invoker`` is expected to be exactly the
same ``GatedCapabilityBinding``-wrapped closure this repo's tool factories
already build (`gymact_dspy_react.py`'s `build_gated_react_tools`,
`powl/runner.py`'s `GatedCapabilityBinding`) -- this module adds no second,
ungated path to a real actuation.

Bounded, not unbounded
-----------------------
A cyclic :class:`~gymact.powl.algebra.ChoiceGraph` (POWL 2.0's iteration
construct) could loop forever if no guard ever matched a real terminating
condition. ``max_choice_transitions`` bounds total transitions taken across
the whole walk; exceeding it raises a real, typed refusal
(:data:`~gymact.powl.refusals.PowlRefusal.TRANSITION_BUDGET_EXHAUSTED`)
rather than hanging.

Five capabilities beyond the minimal walker
--------------------------------------------
1. **Frequency-aware repetition** -- a composite's real
   :class:`~gymact.powl.frequency.Frequency` (``min``/``max``) is
   honored via an optional ``repeat_evaluator`` callback, not silently
   ignored.
2. **Real concurrency** for independent :class:`PartialOrder` branches, via
   ``max_workers`` (default ``1`` -- today's exact serial behavior; pass
   more to get real parallel ``atom_invoker`` calls for a ready set with
   more than one member).
3. **Typed atom-invocation failure** -- an ``atom_invoker`` exception is
   never allowed to propagate raw. It is wrapped in a real
   :data:`~gymact.powl.refusals.PowlRefusal.ATOM_INVOCATION_FAILED`,
   chained (``raise ... from exc``), carrying the real partial
   :class:`ExecutionTrace` accumulated up to the failure.
4. **Checkpoint / resume** -- ``on_step`` is invoked with a real
   :class:`ExecutionCheckpoint` after every real step, and ``resume_from``
   continues a prior walk of the *same* (re-validated, fingerprint-checked)
   model rather than restarting it. Resume is scoped to the top-level node
   only -- see :class:`ExecutionCheckpoint`'s own docstring for the exact,
   stated limitation.
5. **First-class execution context** -- an optional, mutable
   :class:`ExecutionContext` may be threaded through to both callbacks
   (arity-detected, so existing 2-arg/1-arg callers are unaffected).
"""

from __future__ import annotations

import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from gymact.powl._canonical import canonical_json
from gymact.powl.algebra import (
    Atom,
    ChoiceGraph,
    End,
    NodeId,
    PartialOrder,
    PowlNode,
    Silent,
    Start,
)
from gymact.powl.refusals import PowlError, PowlRefusal
from gymact.powl.validate import validate_model

__all__ = [
    "ExecutionStep",
    "ExecutionTrace",
    "ExecutionCheckpoint",
    "ExecutionContext",
    "execute",
]

GuardEvaluator = Callable[..., bool]
AtomInvoker = Callable[..., Any]
RepeatEvaluator = Callable[["NodeId | None", int], bool]
OnStep = Callable[["ExecutionCheckpoint"], None]


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    """One real leaf visited during a walk."""

    kind: str  # "Start" | "End" | "Silent" | "Atom"
    label: str | None = None
    consequence: str | None = None
    result: Any = None
    #: Which repetition of the enclosing composite's ``Frequency`` produced
    #: this step (0 for the first/only repetition).
    repetition_index: int = 0
    #: Whether the real ``atom_invoker`` call for this step raised. The one
    #: legitimate bool field in this module: a real external outcome (did
    #: the invocation raise or not), never an internal decision this module
    #: is modeling as a state -- see the module's own design record.
    failed: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionTrace:
    """The real, ordered record of everything a single :func:`execute` call
    actually visited and invoked -- never a summary reconstructed after the
    fact."""

    steps: tuple[ExecutionStep, ...] = ()
    choice_transitions_taken: int = 0


@dataclass(frozen=True, slots=True)
class ExecutionCheckpoint:
    """Enough real state to resume a top-level walk.

    Captures the accumulated :attr:`steps` and
    :attr:`choice_transitions_taken` exactly as :class:`ExecutionTrace`
    does, plus a ``cursor`` naming where the *top-level* node's walk had
    reached, ``completed_repetitions`` -- how many of the top-level node's
    own ``Frequency`` repetitions had already fully closed before this
    checkpoint was taken -- and ``node_key`` -- a canonical-JSON
    fingerprint of the top-level node being walked, so :func:`execute`
    never resumes a checkpoint against a different model (raises
    :data:`~gymact.powl.refusals.PowlRefusal.CHECKPOINT_NODE_MISMATCH`
    otherwise).

    ``completed_repetitions`` exists so resume never re-derives the
    top-level composite's repetition count from scratch: a checkpoint
    taken mid-repetition N (N > 0) of a top-level ``PartialOrder`` or
    ``ChoiceGraph`` must resume *at* repetition N, not restart the
    mandatory-minimum/maximum accounting at repetition 0 -- restarting it
    would both mislabel resumed steps' ``repetition_index`` and, for a
    ``Frequency(min=k, max=k)``, run more real repetitions across the
    original + resumed calls than the declared ``max`` permits.

    Scoping, stated honestly
    -------------------------
    Resume covers the *top-level* node's own progress only:

    - top-level :class:`~gymact.powl.algebra.ChoiceGraph`: ``cursor``
      is ``("choice", current_index)`` -- the choice node last entered,
      within repetition ``completed_repetitions``.
    - top-level :class:`~gymact.powl.algebra.PartialOrder`: ``cursor``
      is ``("partial_order", frozenset_of_completed_child_indices)``,
      within repetition ``completed_repetitions``.
    - any other top-level kind (``Start``/``End``/``Silent``/``Atom``):
      ``cursor`` is ``("leaf", None)`` -- such a walk has no partial state
      to resume; a checkpoint from one is only ever "already complete."

    A composite nested *inside* one of the top-level node's children is
    always replayed in full when its enclosing top-level unit resumes --
    this module does not claim nested mid-composite resume, and never
    silently pretends to.
    """

    steps: tuple[ExecutionStep, ...]
    choice_transitions_taken: int
    cursor: tuple[str, Any]
    node_key: str
    completed_repetitions: int = 0


class ExecutionContext:
    """A real, typed, mutable carrier for a walk's "current epistemic
    state" -- optional; when supplied via :func:`execute`'s ``context``
    parameter, it is threaded through to both ``guard_evaluator`` and
    ``atom_invoker`` (arity-detected: those callbacks keep working unchanged
    when they don't accept it).

    ``attributes`` is an open bag a caller's guard/invoker may read and
    write freely -- this module never inspects or constrains its contents.
    ``history`` is a **derived, non-authoritative** mirror of the steps
    recorded so far, refreshed by this module after every real step, per
    the no-dual-bookkeeping law: the authoritative record is always the
    :class:`ExecutionTrace` this call returns, never ``context.history``.
    Callers must not independently mutate ``history``.
    """

    __slots__ = ("attributes", "history")

    def __init__(self, attributes: dict[str, Any] | None = None) -> None:
        self.attributes: dict[str, Any] = attributes if attributes is not None else {}
        self.history: list[ExecutionStep] = []


def _node_fingerprint(node: PowlNode) -> Any:
    """A JSON-projectable, canonical-JSON-stable structural fingerprint of
    ``node`` -- stable across processes (unlike ``hash()``, which is salted
    per-process for str-containing dataclasses), used only to detect
    :data:`~gymact.powl.refusals.PowlRefusal.CHECKPOINT_NODE_MISMATCH`.
    """
    if isinstance(node, Start):
        return {"kind": "Start"}
    if isinstance(node, End):
        return {"kind": "End"}
    if isinstance(node, Silent):
        return {"kind": "Silent"}
    if isinstance(node, Atom):
        return {"kind": "Atom", "key": node.key}
    if isinstance(node, PartialOrder):
        return {
            "kind": "PartialOrder",
            "children": [_node_fingerprint(c) for c in node.children],
            "order": sorted([e.src, e.dst] for e in node.order),
            "frequency": [node.frequency.min, node.frequency.max],
        }
    if isinstance(node, ChoiceGraph):
        return {
            "kind": "ChoiceGraph",
            "children": [_node_fingerprint(c) for c in node.children],
            "edges": sorted(
                [e.src, e.dst, e.guard.key if e.guard is not None else None] for e in node.edges
            ),
            "start": node.start,
            "end": node.end,
            "frequency": [node.frequency.min, node.frequency.max],
        }
    raise PowlError(  # pragma: no cover -- validate_model already refuses any other kind
        PowlRefusal.PROHIBITED_NODE_KIND, f"{type(node).__name__} cannot be fingerprinted"
    )


def _node_key(node: PowlNode) -> str:
    return canonical_json(_node_fingerprint(node))


class _CallbackArity:
    """Computed once per :func:`execute` call: whether ``guard_evaluator``
    and ``atom_invoker`` accept a trailing :class:`ExecutionContext`
    argument, so existing 2-arg/1-arg callers keep working unchanged."""

    __slots__ = ("guard_takes_context", "invoker_takes_context")

    def __init__(self, guard_evaluator: GuardEvaluator, atom_invoker: AtomInvoker, context: "ExecutionContext | None") -> None:
        if context is None:
            self.guard_takes_context = False
            self.invoker_takes_context = False
            return
        self.guard_takes_context = _accepts_arity(guard_evaluator, 3)
        self.invoker_takes_context = _accepts_arity(atom_invoker, 2)


def _accepts_arity(fn: Callable[..., Any], n: int) -> bool:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):  # pragma: no cover -- builtins/C callables
        return False
    positional = [
        p
        for p in params.values()
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    has_var_positional = any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in params.values())
    return len(positional) >= n or has_var_positional


class _Counter:
    __slots__ = ("value", "_lock")

    def __init__(self) -> None:
        self.value = 0
        self._lock = threading.Lock()

    def try_increment(self, limit: int) -> bool:
        """Atomically test-and-increment: increments and returns ``True``
        only if the pre-increment value is below ``limit``; otherwise
        leaves ``value`` unchanged and returns ``False``. The check and the
        mutation happen under the same lock acquisition -- unlike a bare
        ``value >= limit`` read followed by a separate later ``increment``,
        two threads can never both observe ``value == limit - 1`` and both
        proceed, which is exactly the race a split check-then-act allowed
        concurrent :class:`ChoiceGraph` transitions to hit."""
        with self._lock:
            if self.value >= limit:
                return False
            self.value += 1
            return True


class _StepSink:
    """Thread-safe accumulator of :class:`ExecutionStep`s, so concurrent
    :class:`PartialOrder` branches can append safely.

    Owns the "does this step also mirror into an :class:`ExecutionContext`'s
    ``history``" decision (via the optional ``context`` constructor arg),
    rather than threading a separate flag through every ``_walk_*``
    function -- a *buffered* per-child sink used during concurrent
    execution (see ``_walk_partial_order_once``) is constructed with
    ``context=None`` so its steps are recorded locally without prematurely
    mirroring into the shared context out of deterministic order; only the
    real, top-level sink (constructed with the caller's real ``context``)
    mirrors, and buffered children are later flushed *through* that real
    sink in deterministic sorted order, so the mirror still happens, just
    at the correct point.
    """

    __slots__ = ("_steps", "_lock", "_on_step", "_transitions", "_top_level_state_fn", "_context")

    def __init__(
        self,
        initial: list[ExecutionStep],
        transitions: _Counter,
        on_step: "OnStep | None",
        top_level_state_fn: Callable[[], tuple[tuple[str, Any], int]],
        context: "ExecutionContext | None" = None,
    ) -> None:
        self._steps = initial
        self._lock = threading.Lock()
        self._on_step = on_step
        self._transitions = transitions
        self._top_level_state_fn = top_level_state_fn
        self._context = context

    def append(self, step: ExecutionStep, *, node_key: str) -> None:
        with self._lock:
            self._steps.append(step)
            snapshot = tuple(self._steps)
        if self._context is not None:
            self._context.history.append(step)
        if self._on_step is not None:
            cursor, completed_repetitions = self._top_level_state_fn()
            self._on_step(
                ExecutionCheckpoint(
                    steps=snapshot,
                    choice_transitions_taken=self._transitions.value,
                    cursor=cursor,
                    node_key=node_key,
                    completed_repetitions=completed_repetitions,
                )
            )

    def snapshot(self) -> tuple[ExecutionStep, ...]:
        with self._lock:
            return tuple(self._steps)


def execute(
    node: PowlNode,
    *,
    guard_evaluator: GuardEvaluator,
    atom_invoker: AtomInvoker,
    max_choice_transitions: int = 64,
    repeat_evaluator: "RepeatEvaluator | None" = None,
    max_workers: int = 1,
    resume_from: "ExecutionCheckpoint | None" = None,
    on_step: "OnStep | None" = None,
    context: "ExecutionContext | None" = None,
) -> ExecutionTrace:
    """Validate, then walk, ``node``.

    ``guard_evaluator(predicate_name, predicate_args)`` (or
    ``guard_evaluator(predicate_name, predicate_args, context)`` when
    ``context`` is supplied and accepted) must be a real, deterministic
    function over the caller's own current epistemic state -- no LLM call.
    ``atom_invoker(atom)`` (or ``atom_invoker(atom, context)``) invokes
    whatever real callable a caller has bound to that atom (a gated tool, a
    pure computation, a verification check); this module never inspects or
    fabricates that callable's behavior.

    ``max_workers`` > 1 runs every node in one :class:`PartialOrder` ready
    set concurrently via a real ``ThreadPoolExecutor`` -- ``atom_invoker``
    (and, if it recurses into nested composites, ``guard_evaluator``) must
    then be safe to call from multiple threads at once; this is the
    caller's responsibility. Trace ordering is unaffected by concurrency:
    steps are always recorded in the same deterministic sorted-index order
    regardless of real completion order.

    ``resume_from`` continues a prior :class:`ExecutionCheckpoint` of this
    *same* ``node`` (re-validated and fingerprint-checked before resuming;
    see :class:`ExecutionCheckpoint` for the exact top-level-only scoping).
    ``on_step`` is invoked with a fresh :class:`ExecutionCheckpoint` after
    every real step -- this module never persists it; that is the caller's
    job.
    """
    validate_model(node)
    node_key = _node_key(node)

    if resume_from is not None and resume_from.node_key != node_key:
        raise PowlError(
            PowlRefusal.CHECKPOINT_NODE_MISMATCH,
            f"checkpoint node_key={resume_from.node_key!r} does not match the node being resumed",
        )

    arity = _CallbackArity(guard_evaluator, atom_invoker, context)
    steps: list[ExecutionStep] = list(resume_from.steps) if resume_from is not None else []
    transitions_taken = _Counter()
    transitions_taken.value = resume_from.choice_transitions_taken if resume_from is not None else 0

    top_cursor_holder: dict[str, Any] = {"cursor": ("leaf", None), "repetition": 0}
    sink = _StepSink(
        steps,
        transitions_taken,
        on_step,
        lambda: (top_cursor_holder["cursor"], top_cursor_holder["repetition"]),
        context=context,
    )

    _walk(
        node,
        guard_evaluator,
        atom_invoker,
        sink,
        transitions_taken,
        max_choice_transitions,
        repeat_evaluator=repeat_evaluator,
        max_workers=max_workers,
        arity=arity,
        context=context,
        node_key=node_key,
        is_top_level=True,
        top_cursor_holder=top_cursor_holder,
        resume_cursor=resume_from.cursor if resume_from is not None else None,
        resume_completed_repetitions=resume_from.completed_repetitions if resume_from is not None else 0,
    )
    return ExecutionTrace(steps=sink.snapshot(), choice_transitions_taken=transitions_taken.value)


def _invoke_guard(
    guard_evaluator: GuardEvaluator,
    predicate_name: str,
    predicate_args: Mapping[str, Any],
    arity: _CallbackArity,
    context: "ExecutionContext | None",
) -> bool:
    if arity.guard_takes_context:
        return guard_evaluator(predicate_name, predicate_args, context)
    return guard_evaluator(predicate_name, predicate_args)


def _invoke_atom(
    atom_invoker: AtomInvoker,
    atom: Atom,
    arity: _CallbackArity,
    context: "ExecutionContext | None",
) -> Any:
    if arity.invoker_takes_context:
        return atom_invoker(atom, context)
    return atom_invoker(atom)


def _walk(
    node: PowlNode,
    guard_evaluator: GuardEvaluator,
    atom_invoker: AtomInvoker,
    sink: _StepSink,
    transitions_taken: _Counter,
    max_choice_transitions: int,
    *,
    repeat_evaluator: "RepeatEvaluator | None",
    max_workers: int,
    arity: _CallbackArity,
    context: "ExecutionContext | None",
    node_key: str,
    is_top_level: bool,
    top_cursor_holder: dict[str, Any],
    resume_cursor: "tuple[str, Any] | None",
    repetition_index: int = 0,
    resume_completed_repetitions: int = 0,
) -> None:
    if isinstance(node, Start):
        sink.append(ExecutionStep(kind="Start", repetition_index=repetition_index), node_key=node_key)
    elif isinstance(node, End):
        sink.append(ExecutionStep(kind="End", repetition_index=repetition_index), node_key=node_key)
    elif isinstance(node, Silent):
        sink.append(ExecutionStep(kind="Silent", repetition_index=repetition_index), node_key=node_key)
    elif isinstance(node, Atom):
        try:
            result = _invoke_atom(atom_invoker, node, arity, context)
        except Exception as exc:
            failure_step = ExecutionStep(
                kind="Atom", label=node.label, consequence=node.consequence, result=None,
                repetition_index=repetition_index, failed=True,
            )
            sink.append(failure_step, node_key=node_key)
            raise PowlError(
                PowlRefusal.ATOM_INVOCATION_FAILED,
                f"atom_invoker raised for atom label={node.label!r}: {exc}",
                partial_trace=ExecutionTrace(steps=sink.snapshot(), choice_transitions_taken=transitions_taken.value),
            ) from exc
        step = ExecutionStep(
            kind="Atom", label=node.label, consequence=node.consequence, result=result,
            repetition_index=repetition_index,
        )
        sink.append(step, node_key=node_key)
    elif isinstance(node, PartialOrder):
        _walk_partial_order_with_frequency(
            node, guard_evaluator, atom_invoker, sink, transitions_taken, max_choice_transitions,
            repeat_evaluator=repeat_evaluator, max_workers=max_workers, arity=arity, context=context,
            node_key=node_key, is_top_level=is_top_level, top_cursor_holder=top_cursor_holder,
            resume_cursor=resume_cursor, resume_completed_repetitions=resume_completed_repetitions,
        )
    elif isinstance(node, ChoiceGraph):
        _walk_choice_graph_with_frequency(
            node, guard_evaluator, atom_invoker, sink, transitions_taken, max_choice_transitions,
            repeat_evaluator=repeat_evaluator, max_workers=max_workers, arity=arity, context=context,
            node_key=node_key, is_top_level=is_top_level, top_cursor_holder=top_cursor_holder,
            resume_cursor=resume_cursor, resume_completed_repetitions=resume_completed_repetitions,
        )
    else:  # pragma: no cover -- validate_model already refuses any other kind
        raise PowlError(PowlRefusal.PROHIBITED_NODE_KIND, f"{type(node).__name__} is not executable")


def _should_run_repetition(node: PartialOrder | ChoiceGraph, completed: int, repeat_evaluator: "RepeatEvaluator | None") -> bool:
    """Decides whether repetition number ``completed`` (0-indexed) should
    run at all -- called *before* every repetition, including the very
    first, so a genuinely zero-repetition composite (``frequency.max == 0``,
    or an evaluator-driven decision to skip an optional composite entirely
    when ``frequency.min == 0``) is representable. A prior design only
    consulted a repetition decision *after* the first repetition had
    already run unconditionally, which silently executed
    ``Frequency(min=0, max=0)`` once -- a real bug, found by a generative
    property-based sweep and fixed forward here. That sweep lives in the
    sibling ``autofde-lab`` repo's ``tests/powl/
    test_guard_executor_property_based.py`` -- gymact's own dependency
    direction means gymact must not depend on autofde-lab, so that file is
    not present, and its sweep is not re-runnable, from within this
    package. As of this writing this package (``gymact``) has no in-repo
    test of its own that exercises this function; that gap is tracked, not
    hidden."""
    freq = node.frequency
    if completed < freq.min:
        return True  # mandatory repetition, never optional
    if freq.max is not None and completed >= freq.max:
        return False
    if repeat_evaluator is None:
        # No evaluator: preserve the documented default -- exactly one
        # repetition when nothing else mandates more or forbids it.
        return completed == 0
    return repeat_evaluator(None, completed)


def _walk_partial_order_with_frequency(
    node: PartialOrder, guard_evaluator, atom_invoker, sink, transitions_taken, max_choice_transitions,
    *, repeat_evaluator, max_workers, arity, context, node_key, is_top_level, top_cursor_holder, resume_cursor,
    resume_completed_repetitions: int = 0,
) -> None:
    already_completed: frozenset[int] = frozenset()
    resumed_repetition = 0
    if is_top_level and resume_cursor is not None and resume_cursor[0] == "partial_order":
        already_completed = frozenset(resume_cursor[1])
        # The checkpoint's own `completed_repetitions` names how many full
        # repetitions had already closed *before* this one started -- never
        # reset to 0 on resume, or a Frequency(min=k, max=k) composite would
        # run extra mandatory repetitions beyond its declared max once the
        # original + resumed executions are totaled (the checkpointed
        # repetition itself resumes at this index, not at index 0).
        resumed_repetition = resume_completed_repetitions

    completed_repetitions = resumed_repetition
    while _should_run_repetition(node, completed_repetitions, repeat_evaluator):
        _walk_partial_order_once(
            node, guard_evaluator, atom_invoker, sink, transitions_taken, max_choice_transitions,
            repeat_evaluator=repeat_evaluator, max_workers=max_workers, arity=arity, context=context,
            node_key=node_key, is_top_level=is_top_level, top_cursor_holder=top_cursor_holder,
            repetition_index=completed_repetitions,
            skip_indices=already_completed if completed_repetitions == resumed_repetition else frozenset(),
        )
        already_completed = frozenset()
        completed_repetitions += 1


def _walk_partial_order_once(
    node: PartialOrder, guard_evaluator, atom_invoker, sink, transitions_taken, max_choice_transitions,
    *, repeat_evaluator, max_workers, arity, context, node_key, is_top_level, top_cursor_holder,
    repetition_index: int, skip_indices: frozenset[int],
) -> None:
    """Deterministic level-by-level Kahn's-algorithm walk (lowest-index-first
    among ready nodes within a level) over ``node.order``'s real transitive
    reduction. Each ready level runs concurrently when ``max_workers`` > 1
    and the level has more than one member; trace ordering always follows
    the deterministic sorted-index order, independent of real completion
    order."""
    n = len(node.children)
    indegree = [0] * n
    adjacency: dict[int, list[int]] = {i: [] for i in range(n)}
    for edge in node.order:
        adjacency[edge.src].append(edge.dst)
        indegree[edge.dst] += 1

    completed: set[int] = set(skip_indices)
    ready = sorted(i for i in range(n) if indegree[i] == 0 and i not in completed)
    # Nodes whose indegree was satisfied entirely by already-completed
    # (resumed) predecessors also need adding to the frontier.
    for i in skip_indices:
        for j in adjacency[i]:
            indegree[j] -= 1
    ready = sorted(set(ready) | {i for i in range(n) if indegree[i] == 0 and i not in completed})

    while len(completed) < n:
        level = [i for i in ready if i not in completed]
        if not level:
            break
        level.sort()
        if is_top_level:
            top_cursor_holder["cursor"] = ("partial_order", frozenset(completed))
            top_cursor_holder["repetition"] = repetition_index

        def _run_child(i: int, target_sink: _StepSink) -> None:
            _walk(
                node.children[i], guard_evaluator, atom_invoker, target_sink, transitions_taken,
                max_choice_transitions, repeat_evaluator=repeat_evaluator, max_workers=max_workers,
                arity=arity, context=context, node_key=node_key, is_top_level=False,
                top_cursor_holder=top_cursor_holder, resume_cursor=None, repetition_index=repetition_index,
            )

        if max_workers > 1 and len(level) > 1:
            # Each concurrently-run child gets its own LOCAL, unmirrored
            # buffer (no on_step, no context mirroring -- see _StepSink's
            # own docstring) so real thread-scheduling nondeterminism never
            # leaks into recorded step order. After every child in this
            # ready-set level has genuinely finished (or failed), every
            # child's buffered steps are flushed into the real `sink` in
            # deterministic sorted-index order -- this is what makes
            # concurrency change *when* work happens without ever changing
            # *what the trace records* or *in what order*.
            def _run_child_buffered(i: int) -> tuple[list[ExecutionStep], BaseException | None]:
                local_steps: list[ExecutionStep] = []
                local_sink = _StepSink(
                    local_steps,
                    transitions_taken,
                    on_step=None,
                    top_level_state_fn=lambda: (top_cursor_holder["cursor"], top_cursor_holder["repetition"]),
                )
                try:
                    _run_child(i, local_sink)
                except BaseException as exc:  # noqa: BLE001 -- deliberately broad: `guard_evaluator`/
                    # `repeat_evaluator` calls reachable from a concurrently-run child are never
                    # wrapped in PowlError the way `atom_invoker` is (see `_invoke_guard`), so a
                    # narrower `except PowlError` here lets a raw exception (e.g. KeyError) escape
                    # `.result()` inside the eager `results = {i: futures[i].result() for i in
                    # level}` comprehension below, aborting it before `results` is ever bound and
                    # silently discarding every *other* sibling child's already-completed,
                    # already-invoked buffered steps -- a real data-loss bug, not merely an
                    # unwrapped-exception cosmetics issue. Capturing every exception here instead
                    # (never propagating out of the submitted callable) guarantees `.result()`
                    # always returns, so the flush loop below always runs for every sibling
                    # regardless of which child failed or how.
                    return local_steps, exc
                return local_steps, None

            with ThreadPoolExecutor(max_workers=min(max_workers, len(level))) as pool:
                futures = {i: pool.submit(_run_child_buffered, i) for i in level}
                results = {i: futures[i].result() for i in level}

            first_error: BaseException | None = None
            for i in level:  # deterministic flush order, regardless of real completion order
                local_steps, error = results[i]
                for step in local_steps:
                    sink.append(step, node_key=node_key)
                if error is not None and first_error is None:
                    first_error = error
            if first_error is not None:
                partial_trace = ExecutionTrace(steps=sink.snapshot(), choice_transitions_taken=transitions_taken.value)
                if isinstance(first_error, PowlError):
                    raise PowlError(
                        first_error.refusal,
                        first_error.detail,
                        partial_trace=partial_trace,
                    ) from first_error.__cause__
                # A non-PowlError exception (guard_evaluator/repeat_evaluator raised something
                # other than PowlError) gets the same typed-refusal + partial_trace treatment
                # every other failure path in this module already gives atom_invoker failures --
                # never left to escape execute() raw and untraceable. The original exception is
                # preserved via `from first_error` (real chaining, inspectable via
                # `__cause__`), never swallowed.
                raise PowlError(
                    PowlRefusal.CHILD_EXECUTION_FAILED,
                    f"concurrently-run PartialOrder child raised {type(first_error).__name__}: {first_error}",
                    partial_trace=partial_trace,
                ) from first_error
        else:
            for i in level:
                _run_child(i, sink)

        for i in level:
            completed.add(i)
            for j in adjacency[i]:
                indegree[j] -= 1
                if indegree[j] == 0 and j not in completed:
                    ready.append(j)

    if is_top_level:
        top_cursor_holder["cursor"] = ("partial_order", frozenset(completed))
        top_cursor_holder["repetition"] = repetition_index


def _walk_choice_graph_with_frequency(
    node: ChoiceGraph, guard_evaluator, atom_invoker, sink, transitions_taken, max_choice_transitions,
    *, repeat_evaluator, max_workers, arity, context, node_key, is_top_level, top_cursor_holder, resume_cursor,
    resume_completed_repetitions: int = 0,
) -> None:
    resume_current: int | None = None
    resumed_repetition = 0
    if is_top_level and resume_cursor is not None and resume_cursor[0] == "choice":
        resume_current = resume_cursor[1]
        # See the identical comment in `_walk_partial_order_with_frequency`:
        # never reset to 0 on resume, or a Frequency(min=k, max=k) composite
        # can be driven past its declared max once the original + resumed
        # repetition counts are totaled.
        resumed_repetition = resume_completed_repetitions

    completed_repetitions = resumed_repetition
    while _should_run_repetition(node, completed_repetitions, repeat_evaluator):
        _walk_choice_graph_once(
            node, guard_evaluator, atom_invoker, sink, transitions_taken, max_choice_transitions,
            arity=arity, context=context, node_key=node_key, is_top_level=is_top_level,
            top_cursor_holder=top_cursor_holder, repetition_index=completed_repetitions,
            resume_current=resume_current if completed_repetitions == resumed_repetition else None,
            repeat_evaluator=repeat_evaluator, max_workers=max_workers,
        )
        resume_current = None
        completed_repetitions += 1


def _walk_choice_graph_once(
    node: ChoiceGraph, guard_evaluator, atom_invoker, sink, transitions_taken, max_choice_transitions,
    *, arity, context, node_key, is_top_level, top_cursor_holder, repetition_index: int,
    resume_current: int | None, repeat_evaluator, max_workers,
) -> None:
    current = resume_current if resume_current is not None else node.start
    if resume_current is None:
        _walk(
            node.children[current], guard_evaluator, atom_invoker, sink, transitions_taken,
            max_choice_transitions, repeat_evaluator=repeat_evaluator, max_workers=max_workers,
            arity=arity, context=context, node_key=node_key, is_top_level=False,
            top_cursor_holder=top_cursor_holder, resume_cursor=None, repetition_index=repetition_index,
        )
    if is_top_level:
        top_cursor_holder["cursor"] = ("choice", current)
        top_cursor_holder["repetition"] = repetition_index

    while current != node.end:
        outgoing = sorted(e for e in node.edges if e.src == current)

        chosen = None
        else_edge = None
        for edge in outgoing:
            if edge.guard is None:
                else_edge = edge
                continue
            if _invoke_guard(guard_evaluator, edge.guard.predicate_name, edge.guard.predicate_args, arity, context):
                chosen = edge
                break
        if chosen is None:
            chosen = else_edge
        if chosen is None:
            raise PowlError(
                PowlRefusal.NO_GUARD_MATCHED,
                f"no guard matched at ChoiceGraph node index {current} and no unguarded 'else' edge exists",
            )

        if not transitions_taken.try_increment(max_choice_transitions):
            raise PowlError(
                PowlRefusal.TRANSITION_BUDGET_EXHAUSTED,
                f"exceeded max_choice_transitions={max_choice_transitions} without reaching end={node.end}",
            )
        current = chosen.dst
        if is_top_level:
            top_cursor_holder["cursor"] = ("choice", current)
            top_cursor_holder["repetition"] = repetition_index
        _walk(
            node.children[current], guard_evaluator, atom_invoker, sink, transitions_taken,
            max_choice_transitions, repeat_evaluator=repeat_evaluator, max_workers=max_workers,
            arity=arity, context=context, node_key=node_key, is_top_level=False,
            top_cursor_holder=top_cursor_holder, resume_cursor=None, repetition_index=repetition_index,
        )
