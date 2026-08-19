"""Deterministic DfCM completion kernel.

This module turns an evidence-bounded set of unfinished work items into a maximal
reversible completion frontier, then manufactures one deterministic cut without
silently granting execution authority.

It is deliberately *not* an autonomous actuator.  The output is CONSTRUCT-only:
SELECT chooses among already-declared reversible moves; DO remains downstream of
GymAct/BRCE authority.  UNKNOWN work never becomes admitted merely because the
planner can enumerate a move for it.
"""

from __future__ import annotations

from functools import reduce
from itertools import islice, product
import json
from operator import mul
from typing import Literal

from blake3 import blake3

from gymact.models import FrozenModel

Standing = Literal[
    "UNKNOWN",
    "PARTIAL_ALIVE",
    "ALIVE",
    "BLOCKED",
    "BUILD_BROKEN",
    "UNSUPPORTED",
    "REFUSED",
]
MoveKind = Literal[
    "PRESERVE",
    "INSPECT",
    "ADAPT",
    "COMPOSE",
    "CONSTRUCT",
    "VERIFY",
    "PUBLISH",
    "DO",
]

_TERMINAL_STANDINGS = frozenset({"ALIVE", "UNSUPPORTED", "REFUSED"})
_CONSTRUCT_KINDS = frozenset(
    {"PRESERVE", "INSPECT", "ADAPT", "COMPOSE", "CONSTRUCT", "VERIFY", "PUBLISH"}
)


class CompletionMove(FrozenModel):
    """One already-known move available for one bounded work item."""

    move_id: str
    item_id: str
    kind: MoveKind
    reversible: bool
    cost: int = 1
    requires_authority: bool = False
    evidence_refs: tuple[str, ...] = ()


class CompletionItem(FrozenModel):
    """Observed state of one unfinished or terminal work item."""

    item_id: str
    standing: Standing
    dependencies: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    moves: tuple[CompletionMove, ...] = ()


class CompletionPlan(FrozenModel):
    """One reversible DfCM branch through the current completion graph."""

    move_ids: tuple[str, ...]
    item_ids: tuple[str, ...]
    total_cost: int


class CompletionFrontier(FrozenModel):
    """Maximal bounded reversible completion space for one exact subject."""

    subject_ref: str
    standing: Standing
    unresolved_items: tuple[str, ...]
    blocked_items: tuple[str, ...]
    total_cardinality: int
    truncated: bool
    plans: tuple[CompletionPlan, ...]
    frontier_digest_blake3: str


class CompletionCut(FrozenModel):
    """Deterministic SELECT result over a manufactured frontier."""

    subject_ref: str
    standing: Standing
    selected: CompletionPlan | None
    reason: str
    frontier_digest_blake3: str
    cut_digest_blake3: str


class CompletionAdmissionError(RuntimeError):
    """Raised when an alleged completion cut crosses the CONSTRUCT/DO fence."""


def _canonical_digest(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return blake3(payload.encode("utf-8")).hexdigest()


def _validate_items(items: tuple[CompletionItem, ...]) -> dict[str, CompletionItem]:
    by_id: dict[str, CompletionItem] = {}
    for item in items:
        if item.item_id in by_id:
            raise ValueError(f"DUPLICATE_COMPLETION_ITEM:{item.item_id}")
        by_id[item.item_id] = item
        for move in item.moves:
            if move.item_id != item.item_id:
                raise ValueError(
                    f"MOVE_ITEM_MISMATCH:{move.move_id}:{move.item_id}:{item.item_id}"
                )
            if move.cost < 0:
                raise ValueError(f"NEGATIVE_MOVE_COST:{move.move_id}:{move.cost}")

    for item in items:
        unknown = tuple(sorted(set(item.dependencies) - set(by_id)))
        if unknown:
            raise ValueError(f"UNKNOWN_COMPLETION_DEPENDENCY:{item.item_id}:{unknown!r}")
    return by_id


def _dependency_ready(item: CompletionItem, by_id: dict[str, CompletionItem]) -> bool:
    return all(by_id[dependency].standing in _TERMINAL_STANDINGS for dependency in item.dependencies)


def _reversible_moves(item: CompletionItem) -> tuple[CompletionMove, ...]:
    return tuple(
        sorted(
            (
                move
                for move in item.moves
                if move.reversible
                and not move.requires_authority
                and move.kind in _CONSTRUCT_KINDS
            ),
            key=lambda move: (move.cost, move.kind, move.move_id),
        )
    )


def manufacture_completion_frontier(
    *,
    subject_ref: str,
    items: tuple[CompletionItem, ...],
    max_plans: int = 4096,
) -> CompletionFrontier:
    """Construct every bounded reversible completion branch without selecting.

    The function is intentionally conservative:
      * terminal ALIVE/UNSUPPORTED/REFUSED items are removed from WIP;
      * dependencies must already be terminal before an item is actionable;
      * DO, irreversible, or authority-requiring moves are excluded from the
        CONSTRUCT frontier rather than being downgraded;
      * an unresolved item with no lawful reversible move is BLOCKED;
      * enumeration is deterministically truncated at ``max_plans`` while the
        exact pre-truncation cardinality remains visible.
    """
    if not subject_ref.strip():
        raise ValueError("EMPTY_COMPLETION_SUBJECT")
    if max_plans < 1:
        raise ValueError("max_plans must be >= 1")

    by_id = _validate_items(items)
    unresolved = tuple(
        item for item in sorted(items, key=lambda item: item.item_id)
        if item.standing not in _TERMINAL_STANDINGS
    )

    actionable: list[tuple[CompletionItem, tuple[CompletionMove, ...]]] = []
    blocked: list[str] = []
    for item in unresolved:
        if not _dependency_ready(item, by_id):
            blocked.append(item.item_id)
            continue
        moves = _reversible_moves(item)
        if not moves:
            blocked.append(item.item_id)
            continue
        actionable.append((item, moves))

    cardinalities = [len(moves) for _item, moves in actionable]
    total_cardinality = reduce(mul, cardinalities, 1) if cardinalities else 0
    truncated = total_cardinality > max_plans

    plans: list[CompletionPlan] = []
    if actionable:
        move_sets = [moves for _item, moves in actionable]
        for combination in islice(product(*move_sets), max_plans):
            plans.append(
                CompletionPlan(
                    move_ids=tuple(move.move_id for move in combination),
                    item_ids=tuple(move.item_id for move in combination),
                    total_cost=sum(move.cost for move in combination),
                )
            )
        plans.sort(key=lambda plan: (plan.total_cost, plan.move_ids))

    unresolved_ids = tuple(item.item_id for item in unresolved)
    blocked_ids = tuple(sorted(blocked))
    if not unresolved_ids:
        standing: Standing = "ALIVE"
    elif blocked_ids:
        standing = "BLOCKED"
    else:
        standing = "PARTIAL_ALIVE"

    digest_payload = {
        "subject_ref": subject_ref,
        "standing": standing,
        "unresolved_items": unresolved_ids,
        "blocked_items": blocked_ids,
        "total_cardinality": total_cardinality,
        "truncated": truncated,
        "plans": [plan.model_dump(mode="json") for plan in plans],
    }
    return CompletionFrontier(
        subject_ref=subject_ref,
        standing=standing,
        unresolved_items=unresolved_ids,
        blocked_items=blocked_ids,
        total_cardinality=total_cardinality,
        truncated=truncated,
        plans=tuple(plans),
        frontier_digest_blake3=_canonical_digest(digest_payload),
    )


def select_completion_cut(frontier: CompletionFrontier) -> CompletionCut:
    """SELECT the deterministic cheapest reversible branch; never actuate it."""
    selected = frontier.plans[0] if frontier.plans else None
    if frontier.standing == "ALIVE":
        standing: Standing = "ALIVE"
        reason = "SUBJECT_ALREADY_ALIVE"
    elif frontier.blocked_items:
        standing = "BLOCKED"
        reason = f"BLOCKED_ITEMS:{','.join(frontier.blocked_items)}"
    elif selected is None:
        standing = "BLOCKED"
        reason = "NO_REVERSIBLE_COMPLETION_PLAN"
    else:
        standing = "PARTIAL_ALIVE"
        reason = "REVERSIBLE_CUT_SELECTED_CONSTRUCT_ONLY"

    digest_payload = {
        "subject_ref": frontier.subject_ref,
        "frontier_digest_blake3": frontier.frontier_digest_blake3,
        "standing": standing,
        "selected": selected.model_dump(mode="json") if selected else None,
        "reason": reason,
    }
    return CompletionCut(
        subject_ref=frontier.subject_ref,
        standing=standing,
        selected=selected,
        reason=reason,
        frontier_digest_blake3=frontier.frontier_digest_blake3,
        cut_digest_blake3=_canonical_digest(digest_payload),
    )


def admit_completion_cut(
    *,
    cut: CompletionCut,
    items: tuple[CompletionItem, ...],
) -> CompletionCut:
    """Prove a cut is still CONSTRUCT-only against the admitted source items.

    This is the authority fence.  A move can only be admitted here when the exact
    move id exists on the exact item and is reversible, authority-free, and not
    DO.  Anything else is a typed refusal rather than ambient execution authority.
    """
    by_id = _validate_items(items)
    if cut.selected is None:
        if cut.standing == "ALIVE":
            return cut
        raise CompletionAdmissionError(f"REFUSED:NO_SELECTED_CUT:{cut.reason}")

    for item_id, move_id in zip(cut.selected.item_ids, cut.selected.move_ids, strict=True):
        item = by_id.get(item_id)
        if item is None:
            raise CompletionAdmissionError(f"REFUSED:UNKNOWN_ITEM:{item_id}")
        move = next((candidate for candidate in item.moves if candidate.move_id == move_id), None)
        if move is None:
            raise CompletionAdmissionError(f"REFUSED:UNKNOWN_MOVE:{item_id}:{move_id}")
        if move.kind == "DO":
            raise CompletionAdmissionError(f"REFUSED:DO_REQUIRES_BRCE:{move_id}")
        if not move.reversible:
            raise CompletionAdmissionError(f"REFUSED:IRREVERSIBLE_MOVE:{move_id}")
        if move.requires_authority:
            raise CompletionAdmissionError(f"REFUSED:AUTHORITY_REQUIRED:{move_id}")
        if move.kind not in _CONSTRUCT_KINDS:
            raise CompletionAdmissionError(f"REFUSED:UNSUPPORTED_MOVE_KIND:{move_id}:{move.kind}")

    return cut


def manufacture_and_admit_completion(
    *,
    subject_ref: str,
    items: tuple[CompletionItem, ...],
    max_plans: int = 4096,
) -> tuple[CompletionFrontier, CompletionCut]:
    """Convenience parse→construct→select→admit pipeline with zero DO."""
    frontier = manufacture_completion_frontier(
        subject_ref=subject_ref,
        items=items,
        max_plans=max_plans,
    )
    cut = select_completion_cut(frontier)
    if cut.selected is not None or cut.standing == "ALIVE":
        admit_completion_cut(cut=cut, items=items)
    return frontier, cut
