"""Connect admitted POWL v2 process documents to GymAct execution surfaces.

Planning and POWL construction stay upstream. This module only recovers a
deterministic structural fire order and dispatches caller-supplied bindings.
Bindings never manufacture authority: the reference-kernel path consumes
ActuationIntent objects and the production path consumes complete BRCE
BrokerRequest objects carrying an already-constructed PreparedAction and an
identity-bound ExecutionGrant.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

from gymact.brce import BRCEBroker, BrokerRequest
from gymact.crown_runtime import VerifiedTransition
from gymact.kernel import GymAct
from gymact.models import ActuationIntent, ActuationResult
from gymact.powl.algebra import Atom, PartialOrder, PowlNode
from gymact.powl.executor import DEFAULT_BOUND, INITIAL_MARKING, enabled, fire, is_final
from gymact.powl.turtle_bridge import BridgeError, parse_powl_turtle, powl_model_to_node

__all__ = [
    "PowlReplayRefusal",
    "parse_admitted_powl_document",
    "replay_admitted_powl_via_brce",
    "replay_admitted_powl_via_kernel",
]


class PowlReplayRefusal(RuntimeError):
    """Typed replay refusal; never a silent partial replay."""


def parse_admitted_powl_document(turtle: str) -> PowlNode:
    """Parse an already-admitted POWL2 Turtle document into a PowlNode."""
    try:
        model = parse_powl_turtle(turtle)
        return powl_model_to_node(model)
    except BridgeError as exc:
        raise PowlReplayRefusal(f"REFUSED:{exc}") from exc


def _real_fire_order(tree: PowlNode) -> tuple[Atom, ...]:
    """Recover a deterministic linear extension using the real POWL executor."""
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


T = TypeVar("T")


def _require_binding(binding: Mapping[str, T], action: str) -> T:
    value = binding.get(action)
    if value is None:
        raise PowlReplayRefusal(
            f"REFUSED:UNBOUND_IMPLEMENTS_ACTION:action={action!r}"
        )
    return value


async def replay_admitted_powl_via_kernel(
    kernel: GymAct,
    tree: PowlNode,
    *,
    intent_binding: Mapping[str, ActuationIntent],
) -> tuple[ActuationResult, ...]:
    """Reference/conformance replay through the compatibility kernel act port."""
    fire_order = _real_fire_order(tree)
    if not fire_order:
        raise PowlReplayRefusal("REFUSED:EMPTY_DOCUMENT")

    results: list[ActuationResult] = []
    for atom in fire_order:
        intent = _require_binding(intent_binding, atom.action)
        results.append(await kernel.act(intent))
    return tuple(results)


async def replay_admitted_powl_via_brce(
    broker: BRCEBroker,
    tree: PowlNode,
    *,
    request_binding: Mapping[str, BrokerRequest],
) -> tuple[VerifiedTransition, ...]:
    """Production POWL replay through BRCE's exclusive DO boundary.

    The POWL graph determines only structural order. Every fired action must
    already be bound to a complete BrokerRequest. Therefore this bridge cannot
    mint authority, infer capabilities, construct an ExecutionGrant, or call a
    production runtime's raw ``act`` port. ``BRCEBroker.execute`` performs
    identity/revision admission, sealed provider actuation, and independent
    postcondition verification; only its resulting VerifiedTransition may carry
    ALIVE standing.
    """
    fire_order = _real_fire_order(tree)
    if not fire_order:
        raise PowlReplayRefusal("REFUSED:EMPTY_DOCUMENT")

    transitions: list[VerifiedTransition] = []
    for atom in fire_order:
        request = _require_binding(request_binding, atom.action)
        transitions.append(await broker.execute(request))
    return tuple(transitions)
