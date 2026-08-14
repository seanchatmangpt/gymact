# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Content-addressed identity for POWL 2.0 nodes.

Digests are Merkle-style and built over
:func:`gymact.powl._canonical.canonical_json` + ``sha256``. Two invariants
are load-bearing:

1. Only the transitive **reduction** enters a digest; the closure is a derived
   execution aid and never contributes.
2. Every set is serialized in a sorted canonical order, so Python's
   ``frozenset`` iteration order can never leak into a digest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gymact.powl._canonical import canonical_json
from gymact.powl._canonical import sha256 as _sha256
from gymact.powl.algebra import (
    Atom,
    ChoiceGraph,
    End,
    PartialOrder,
    PowlNode,
    Silent,
    Start,
    _action_identity,
)
from gymact.powl.frequency import Frequency
from gymact.powl.refusals import PowlError, PowlRefusal

__all__ = ["activity_sha256", "node_id", "node_structure", "OccurrenceKey"]


def activity_sha256(atom: Atom) -> str:
    """Content hash of an :class:`~gymact.powl.algebra.Atom`.

    Covers ``{label, action identity, bindings, consequence}`` — the same
    fields :attr:`~gymact.powl.algebra.Atom.key` folds in (see that
    attribute's docstring: "consequence also participates in key"). This
    function must stay a strict re-derivation of ``Atom.key``'s own field
    set rather than an independent enumeration of "what matters" for an
    Atom's identity: two independently-chosen field lists are exactly the
    dual-bookkeeping pattern this package's identity layer exists to avoid
    (see ``.claude/rules/no-dual-bookkeeping.md``), and diverging on
    ``consequence`` in particular would let two atoms differing only in
    whether they have a real world-effect (``PURE`` vs ``DO``) collide
    under this digest while ``guard_executor``'s own checkpoint fingerprint
    (which uses ``Atom.key`` directly) tells them apart.
    """
    if not isinstance(atom, Atom):
        raise PowlError(
            PowlRefusal.PROHIBITED_NODE_KIND,
            f"activity_sha256 expects Atom, got {type(atom).__name__}",
        )
    return _sha256(
        {
            "label": atom.label,
            "action": _action_identity(atom.action),
            "bindings": dict(atom.bindings),
            "consequence": atom.consequence,
        }
    )


def _freq(f: Frequency) -> dict[str, Any]:
    return {"min": f.min, "max": f.max}


def node_structure(node: PowlNode) -> dict[str, Any]:
    """Canonical, order-independent structural description of ``node``."""
    if isinstance(node, Start):
        return {"kind": "Start"}
    if isinstance(node, End):
        return {"kind": "End"}
    if isinstance(node, Silent):
        return {"kind": "Silent"}
    if isinstance(node, Atom):
        return {"kind": "Atom", "activity": activity_sha256(node)}
    if isinstance(node, PartialOrder):
        return {
            "kind": "PartialOrder",
            "children": [node_id(c) for c in node.children],
            # reduction only, sorted — never the closure, never set order
            "order": sorted([e.src, e.dst] for e in node.order),
            "frequency": _freq(node.frequency),
        }
    if isinstance(node, ChoiceGraph):
        return {
            "kind": "ChoiceGraph",
            "children": [node_id(c) for c in node.children],
            # guard participates in edge identity — a guarded transition and
            # an unconditional one (or two transitions guarded by different
            # predicates) between the same (src, dst) pair are genuinely
            # different edges. Mirrors guard_executor._node_fingerprint's
            # ChoiceGraph branch, which folds in ``e.guard.key`` for the same
            # reason; see this module's docstring on
            # ``no-dual-bookkeeping``-style divergence.
            "edges": sorted(
                [e.src, e.dst, e.guard.key if e.guard is not None else None] for e in node.edges
            ),
            "start": node.start,
            "end": node.end,
            "frequency": _freq(node.frequency),
        }
    raise PowlError(
        PowlRefusal.PROHIBITED_NODE_KIND,
        f"{type(node).__name__} is not a POWL 2.0 node kind",
    )


def node_id(node: PowlNode) -> str:
    """Recursive Merkle identity of ``node``."""
    return _sha256(canonical_json(node_structure(node)))


@dataclass(frozen=True, slots=True)
class OccurrenceKey:
    """Identity of one occurrence of an activity within a traversal context."""

    activity_sha256: str
    occurrence_index: int
    context_sha256: str
