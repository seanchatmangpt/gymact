# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Export typed POWL refusals as castle ``NegationRecord`` JSON dicts.

A :class:`gymact.powl.refusals.PowlRefusal` is a verdict about *shape*.
Exactly one question separates a refusal that is honest negative evidence
from one that is not:

    "did the refusal arise because something was looked for and absent?"

Only refusals whose semantics are literally absence-of-evidence may become
a ``NegationRecord`` (predicate = the refusal class, subject = the
episode/receipt id, ``searched_at`` = caller-supplied refusal timestamp,
``searched_by = "gymact-powl"``). Everything else is a structural verdict,
a resource limit, or an execution failure — none of those is an honest
"we searched and found nothing" claim, and asserting one as a negation
would manufacture negative evidence.

Target shape (pinned from ``~/castle/src/negative_evidence.rs:48``,
``pub struct NegationRecord`` — serde default field names, camel-free):

.. code-block:: rust

    pub struct NegationRecord {
        pub predicate: String,
        pub subject: String,
        pub searched_at: String,   // RFC 3339
        pub searched_by: String,
    }

Key surface is ``(subject, predicate)`` (``negative_evidence.rs:63``).
"""

from __future__ import annotations

from typing import Any

from gymact.powl.refusals import PowlRefusal

__all__ = [
    "MAPPED_REFUSAL_CLASSES",
    "REFUSAL_CLASS_SEMANTICS",
    "NEGATION_RECORD_FIELDS",
    "refusal_to_negation_record",
]

#: ``searched_by`` identity for records minted from POWL refusals.
SEARCHED_BY = "gymact-powl"

#: Field set of the Rust ``NegationRecord`` serde shape (see pinned copy above).
NEGATION_RECORD_FIELDS = frozenset(
    {"predicate", "subject", "searched_at", "searched_by"}
)

#: Refusal classes whose semantics are literally "searched, absent".
#:
#: - ``DANGLING_REFERENCE`` — a node references a target that was looked up
#:   in the shape and found absent; the predicate names that lookup.
#: - ``NO_GUARD_MATCHED`` — every guard was evaluated and none matched; an
#:   honest absence-of-match finding over the searched guard set.
MAPPED_REFUSAL_CLASSES: frozenset[str] = frozenset(
    {
        PowlRefusal.DANGLING_REFERENCE,
        PowlRefusal.NO_GUARD_MATCHED,
    }
)

#: Refusal classes that are NOT absence-of-evidence, with reasons.
#:
#: These are deliberately *not* mapped. Flattening them into negations
#: would record "no evidence of X" when the real verdict is "X is
#: malformed/over-budget/failed", which is a claim about the subject's
#: constitution, not about a missing observation.
REFUSAL_CLASS_SEMANTICS: dict[str, str] = {
    PowlRefusal.CYCLIC_PARTIAL_ORDER: (
        "structural verdict: the shape contains a cycle — a positive "
        "finding about the graph, not an absence"
    ),
    PowlRefusal.INVALID_CHOICE: (
        "structural verdict: a choice construct is malformed"
    ),
    PowlRefusal.INVALID_CHOICE_ARITY: (
        "structural verdict: choice arity is a positive mis-measurement"
    ),
    PowlRefusal.IRREDUCIBLE_PROJECTION: (
        "structural verdict: projection cannot be reduced — a property of "
        "the shape, not a missing observation"
    ),
    PowlRefusal.LANGUAGE_MISMATCH: (
        "contradiction, not absence: two language descriptions disagree — "
        "the castle ledger handles contradictions via "
        "REFUSED:EVIDENCE_CONTRADICTION, not via negation"
    ),
    PowlRefusal.CHOICE_GRAPH_DISCONNECTED: (
        "structural verdict: connectivity failure — a positive finding "
        "about the graph"
    ),
    PowlRefusal.MULTI_BOUNDARY_CHOICE_GRAPH: (
        "structural verdict: multiple boundary choices found — "
        "over-evidence, not absence"
    ),
    PowlRefusal.DEPTH_EXCEEDED: (
        "resource limit: the search did not complete, so 'absent' would "
        "overclaim — an incomplete search is not evidence of absence"
    ),
    PowlRefusal.DANGLING_REFERENCE: (
        "mapped: a referenced node was looked up and found absent"
    ),
    PowlRefusal.NOT_TRANSITIVELY_REDUCED: (
        "structural verdict: reducibility is a shape property, not an "
        "observation gap"
    ),
    PowlRefusal.EDGE_TYPE_MISMATCH: (
        "contradiction, not absence: an edge exists but with the wrong type"
    ),
    PowlRefusal.INVALID_PARTIAL_ORDER_ARITY: (
        "structural verdict: arity mis-measurement"
    ),
    PowlRefusal.INVALID_FREQUENCY: (
        "structural verdict: frequency annotation malformed"
    ),
    PowlRefusal.PROHIBITED_NODE_KIND: (
        "contradiction, not absence: a node of a disallowed kind is present"
    ),
    PowlRefusal.BOUND_EXHAUSTED: (
        "resource limit: incomplete search — not evidence of absence"
    ),
    PowlRefusal.AMBIGUOUS_CHOICE_GUARD: (
        "contradiction/over-evidence: multiple guards matched; nothing is "
        "absent"
    ),
    PowlRefusal.NO_GUARD_MATCHED: (
        "mapped: all guards were evaluated and none matched — honest "
        "absence-of-match over the searched set"
    ),
    PowlRefusal.TRANSITION_BUDGET_EXHAUSTED: (
        "resource limit: the transition budget ran out mid-search; the "
        "remainder is unsearched, so absence would overclaim"
    ),
    PowlRefusal.ATOM_INVOCATION_FAILED: (
        "execution failure: the atom ran and errored — a positive event, "
        "not a missing observation"
    ),
    PowlRefusal.CHILD_EXECUTION_FAILED: (
        "execution failure: a child ran and errored — a positive event"
    ),
    PowlRefusal.CHECKPOINT_NODE_MISMATCH: (
        "contradiction, not absence: the node found is not the node "
        "expected"
    ),
}


def refusal_to_negation_record(
    *,
    refusal: PowlRefusal | str,
    subject: str,
    searched_at: str,
    detail: str = "",
) -> dict[str, Any] | None:
    """Map one gymact refusal event to a ``NegationRecord`` JSON dict.

    Args:
        refusal: the refusal class (a :class:`PowlRefusal` or its string
            value).
        subject: the episode/receipt id the refusal was raised against.
        searched_at: caller-supplied refusal timestamp (RFC 3339). The
            module is pure and never reads a clock.
        detail: optional refusal detail. Currently unused for the record
            body; accepted so call sites can pass a ``PowlError.detail``
            through unchanged.

    Returns:
        A dict with exactly the four pinned ``NegationRecord`` fields, or
        ``None`` for any refusal class in ``REFUSAL_CLASS_SEMANTICS`` (and
        for any unknown class — totality is asserted by tests over the
        enum, so a future class added to :class:`PowlRefusal` without a
        mapping/exclusion entry fails the sabotage test).

    Raises:
        ValueError: if ``subject`` or ``searched_at`` is empty — the castle
            admission gate refuses incomplete negations
            (``REFUSED:NEGATION_INCOMPLETE`` upstream), so we never mint one.
    """
    if not subject:
        raise ValueError("subject must be non-empty (REFUSED:NEGATION_INCOMPLETE)")
    if not searched_at:
        raise ValueError("searched_at must be non-empty (REFUSED:NEGATION_INCOMPLETE)")

    refusal_value = refusal.value if isinstance(refusal, PowlRefusal) else str(refusal)

    if refusal_value not in MAPPED_REFUSAL_CLASSES:
        # Includes every excluded class and any unknown class: a mapped
        # record is only minted for classes whose semantics are absence.
        return None

    return {
        "predicate": refusal_value,
        "subject": subject,
        "searched_at": searched_at,
        "searched_by": SEARCHED_BY,
    }
