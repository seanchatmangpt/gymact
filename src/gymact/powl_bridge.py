"""Connects an already-admitted POWL v2 process document (the shape
`autofde_lab.fabric.powl.project_plan_to_powl` already produces from a real
PDDL plan) to gymact's real `kernel.act()` -- the POWL-native sibling of
`gymact.gdmcp_bpmn_bridge`, same two-phase shape, same invariant.

Per `docs/actuation-layer-scope.md`: gymact is the BRCE/actuation/receipt
layer only. PDDL planning and POWL-graph *construction* happen upstream, in
autofde-lab -- this module never constructs a POWL graph, never plans, and
never guesses a capability from an activity label. It does exactly two
things: (1) real structural replay of an already-parsed POWL tree via
`gymact.powl.executor`'s own `enabled()`/`fire()`/`is_final()` to recover a
real, deterministic fire order (no kernel call in this phase -- mirrors
`gdmcp_bpmn_bridge._real_fire_order`'s "record, never actuate" split), then
(2) real, sequential `kernel.act()` calls in that order, driven by a
caller-supplied, explicit `label -> ActuationIntent` binding -- the bridge
determines *order*, never *authority*.

Real structural replay of `gymact.powl.turtle_bridge.powl_model_to_node`'s
output is scoped, by that module's own documented refusal, to a flat
`PartialOrder` of `Atom`s (or a bare `Atom`) -- no `ChoiceGraph`, since
`project_plan_to_powl`'s Turtle vocabulary has no construct for one. Within
that scope, multiple leaves may be structurally concurrent (unordered by
any `powl2:precedes` edge); this module picks the lowest-`NodePath`
enabled leaf at each step as a deterministic, honest linear extension --
stated explicitly, not silently presented as the graph's own single truth
about concurrency (`gymact.powl.executor.enabled()`'s own docstring: "a
set, never an ordered choice").
"""

from __future__ import annotations

from collections.abc import Mapping

from gymact.kernel import GymAct
from gymact.models import ActuationIntent, ActuationResult
from gymact.powl.algebra import Atom, PartialOrder, PowlNode
from gymact.powl.executor import INITIAL_MARKING, DEFAULT_BOUND, enabled, fire, is_final
from gymact.powl.turtle_bridge import BridgeError, parse_powl_turtle, powl_model_to_node

__all__ = [
    "PowlReplayRefusal",
    "parse_admitted_powl_document",
    "replay_admitted_powl_via_kernel",
]


class PowlReplayRefusal(RuntimeError):
    """Raised for a real, named failure -- an unparseable/out-of-scope
    document, a structural deadlock, or a fired activity whose
    `implementsAction` label has no entry in the caller's intent binding.
    Never a silent partial replay."""


def parse_admitted_powl_document(turtle: str) -> PowlNode:
    """Real parse of an already-admitted POWL2 Turtle document into an
    executor-consumable `PowlNode` tree -- `parse_powl_turtle` (real
    `rdflib`-based decode) then `powl_model_to_node` (the existing,
    already-tested Turtle-model -> algebra bridge). Raises
    `PowlReplayRefusal` if either step refuses, re-typing the real
    `BridgeError` rather than letting a bridge-internal exception type leak
    across this module's own boundary."""
    try:
        model = parse_powl_turtle(turtle)
        return powl_model_to_node(model)
    except BridgeError as exc:
        raise PowlReplayRefusal(f"REFUSED:{exc}") from exc


def _real_fire_order(tree: PowlNode) -> tuple[Atom, ...]:
    """Real, deterministic structural replay via `gymact.powl.executor` --
    no kernel call happens in this function. At each step, fires the
    lowest-`NodePath` leaf currently enabled (a real, honest linear
    extension of the partial order, not a claim that the graph itself is
    totally ordered)."""
    marking = INITIAL_MARKING
    order: list[Atom] = []
    seen_paths: set[tuple[int, ...]] = set()
    max_steps = DEFAULT_BOUND.max_activity_fires + 1
    for _ in range(max_steps):
        if is_final(tree, marking):
            return tuple(order)
        live = enabled(tree, marking, DEFAULT_BOUND)
        live = frozenset(path for path in live if path not in seen_paths)
        if not live:
            raise PowlReplayRefusal(
                f"REFUSED:STRUCTURAL_DEADLOCK:marking={marking.digest_material()!r}"
            )
        path = min(live)
        node = tree if path == () else _node_at(tree, path)
        if not isinstance(node, Atom):
            raise PowlReplayRefusal(
                f"REFUSED:UNSUPPORTED_NODE_SHAPE:path={path!r}:type={type(node).__name__}"
            )
        marking = fire(tree, marking, path, bound=DEFAULT_BOUND)
        seen_paths.add(path)
        order.append(node)
    raise PowlReplayRefusal(f"REFUSED:BOUND_EXHAUSTED:max_steps={max_steps}")


def _node_at(tree: PowlNode, path: tuple[int, ...]) -> PowlNode:
    node = tree
    for idx in path:
        if not isinstance(node, PartialOrder):
            raise PowlReplayRefusal(
                f"REFUSED:UNSUPPORTED_NODE_SHAPE:path {path} descends into a non-PartialOrder"
            )
        node = node.children[idx]
    return node


async def replay_admitted_powl_via_kernel(
    kernel: GymAct,
    tree: PowlNode,
    *,
    intent_binding: Mapping[str, ActuationIntent],
) -> tuple[ActuationResult, ...]:
    """Real, two-phase replay. Phase 1 (sync, no kernel call): real
    structural replay of `tree` via `gymact.powl.executor` recovers the
    real fire order as a tuple of `Atom`s. Phase 2 (async): that real order
    drives real, sequential `kernel.act(intent_binding[atom.action])`
    calls -- the only real actuation path, `CapabilityScope`/
    `AuthorityResolver` unchanged, exactly `gdmcp_bpmn_bridge
    .replay_compiled_program_via_bpmn`'s own pattern. Raises
    `PowlReplayRefusal` if any fired `Atom.action` has no entry in
    `intent_binding` -- never invents or guesses a capability from a
    label."""
    fire_order = _real_fire_order(tree)
    if not fire_order:
        raise PowlReplayRefusal("REFUSED:EMPTY_DOCUMENT")

    results: list[ActuationResult] = []
    for atom in fire_order:
        intent = intent_binding.get(atom.action)
        if intent is None:
            raise PowlReplayRefusal(
                f"REFUSED:UNBOUND_IMPLEMENTS_ACTION:action={atom.action!r}"
            )
        result = await kernel.act(intent)
        results.append(result)
    return tuple(results)
