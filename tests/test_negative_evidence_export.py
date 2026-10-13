# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Court: typed-refusal -> NegationRecord export (castle parity).

Pinned Rust source (~/castle/src/negative_evidence.rs:48-57):

.. code-block:: rust

    pub struct NegationRecord {
        /// What was looked for — predicate/query/metric identity.
        pub predicate: String,
        /// Where it was looked — the subject of the would-be evidence.
        pub subject: String,
        /// When the search happened (RFC 3339).
        pub searched_at: String,
        /// By whom.
        pub searched_by: String,
    }

Key surface: ``(subject, predicate)`` (``negative_evidence.rs:63``).
"""

from __future__ import annotations

import json

import pytest

from gymact.negative_evidence import (
    MAPPED_REFUSAL_CLASSES,
    NEGATION_RECORD_FIELDS,
    REFUSAL_CLASS_SEMANTICS,
    SEARCHED_BY,
    refusal_to_negation_record,
)
from gymact.powl.refusals import PowlRefusal

# --- pinned NegationRecord field set (read from the comment-pinned copy) ---

PINNED_NEGATION_RECORD_FIELDS = frozenset(
    {"predicate", "subject", "searched_at", "searched_by"}
)


class TestShapeConformance:
    def test_pinned_field_set_matches_module(self):
        assert NEGATION_RECORD_FIELDS == PINNED_NEGATION_RECORD_FIELDS

    def test_mapped_record_has_exactly_the_pinned_fields(self):
        record = refusal_to_negation_record(
            refusal=PowlRefusal.NO_GUARD_MATCHED,
            subject="episode-1",
            searched_at="2026-10-13T00:00:00Z",
        )
        assert set(record) == PINNED_NEGATION_RECORD_FIELDS
        assert record["predicate"] == "NO_GUARD_MATCHED"
        assert record["subject"] == "episode-1"
        assert record["searched_at"] == "2026-10-13T00:00:00Z"
        assert record["searched_by"] == SEARCHED_BY

    def test_record_json_round_trips_like_serde(self):
        record = refusal_to_negation_record(
            refusal=PowlRefusal.DANGLING_REFERENCE,
            subject="receipt-abc",
            searched_at="2026-10-13T01:02:03Z",
        )
        # serde_json round-trip parity: field names survive a JSON cycle.
        cycled = json.loads(json.dumps(record))
        assert cycled == record
        assert set(cycled) == PINNED_NEGATION_RECORD_FIELDS

    def test_searched_by_is_gymact_powl(self):
        record = refusal_to_negation_record(
            refusal="NO_GUARD_MATCHED",
            subject="s",
            searched_at="t",
        )
        assert record["searched_by"] == "gymact-powl"

    def test_incomplete_negation_refused(self):
        # castle: REFUSED:NEGATION_INCOMPLETE for empty predicate/subject/
        # searched_by; here subject/searched_at emptiness is the caller's
        # incomplete-negation failure mode.
        with pytest.raises(ValueError):
            refusal_to_negation_record(
                refusal=PowlRefusal.NO_GUARD_MATCHED, subject="", searched_at="t"
            )
        with pytest.raises(ValueError):
            refusal_to_negation_record(
                refusal=PowlRefusal.NO_GUARD_MATCHED, subject="s", searched_at=""
            )


class TestMappedSemantics:
    def test_only_honest_absences_are_mapped(self):
        assert MAPPED_REFUSAL_CLASSES == frozenset(
            {PowlRefusal.DANGLING_REFERENCE, PowlRefusal.NO_GUARD_MATCHED}
        )

    def test_dangling_reference_maps(self):
        assert refusal_to_negation_record(
            refusal=PowlRefusal.DANGLING_REFERENCE, subject="s", searched_at="t"
        ) == {
            "predicate": "DANGLING_REFERENCE",
            "subject": "s",
            "searched_at": "t",
            "searched_by": "gymact-powl",
        }

    def test_structural_refusal_is_not_a_negation(self):
        # CYCLIC_PARTIAL_ORDER is a positive finding about the graph.
        assert (
            refusal_to_negation_record(
                refusal=PowlRefusal.CYCLIC_PARTIAL_ORDER, subject="s", searched_at="t"
            )
            is None
        )

    def test_resource_limit_is_not_a_negation(self):
        # An incomplete search must not claim absence.
        for refusal in (
            PowlRefusal.DEPTH_EXCEEDED,
            PowlRefusal.BOUND_EXHAUSTED,
            PowlRefusal.TRANSITION_BUDGET_EXHAUSTED,
        ):
            assert (
                refusal_to_negation_record(refusal=refusal, subject="s", searched_at="t")
                is None
            )

    def test_execution_failure_is_not_a_negation(self):
        for refusal in (
            PowlRefusal.ATOM_INVOCATION_FAILED,
            PowlRefusal.CHILD_EXECUTION_FAILED,
        ):
            assert (
                refusal_to_negation_record(refusal=refusal, subject="s", searched_at="t")
                is None
            )


class TestTotality:
    def test_every_refusal_class_is_mapped_or_documented(self):
        # No silent class: every PowlRefusal member appears in the
        # semantics table, and the mapped set is exactly the ones the
        # table marks "mapped:".
        documented = frozenset(REFUSAL_CLASS_SEMANTICS)
        assert frozenset(PowlRefusal) <= documented
        marked_mapped = frozenset(
            cls
            for cls, reason in REFUSAL_CLASS_SEMANTICS.items()
            if reason.startswith("mapped:")
        )
        assert marked_mapped == MAPPED_REFUSAL_CLASSES

    def test_every_class_is_decided(self):
        def decide(refusal):
            record = refusal_to_negation_record(
                refusal=refusal, subject="s", searched_at="t"
            )
            return "mapped" if record is not None else "excluded"

        for refusal in PowlRefusal:
            assert decide(refusal) in {"mapped", "excluded"}


class TestDeterminism:
    def test_same_inputs_same_record(self):
        a = refusal_to_negation_record(
            refusal=PowlRefusal.NO_GUARD_MATCHED,
            subject="episode-9",
            searched_at="2026-10-13T00:00:00Z",
        )
        b = refusal_to_negation_record(
            refusal="NO_GUARD_MATCHED",
            subject="episode-9",
            searched_at="2026-10-13T00:00:00Z",
        )
        assert a == b
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

    def test_pure_no_clock_no_state(self):
        # Two calls at "different times" with the same caller-supplied
        # timestamp produce identical bytes; the module reads no clock.
        one = refusal_to_negation_record(
            refusal=PowlRefusal.DANGLING_REFERENCE, subject="s", searched_at="T0"
        )
        two = refusal_to_negation_record(
            refusal=PowlRefusal.DANGLING_REFERENCE, subject="s", searched_at="T0"
        )
        assert one is not two
        assert one == two


class TestSabotageTwin:
    def test_new_unmapped_class_fails_totality(self):
        # Sabotage: simulate PowlRefusal gaining a new member with no
        # semantics-table entry. The same totality predicate the court
        # uses must FAIL on the extended class list — proving the court
        # is non-vacuous (reverting the fix = adding an undocumented
        # class = this twin goes red).
        forged = "SAFEGUARD_TWIN_SHOULD_NOT_EXIST"
        assert forged not in frozenset(PowlRefusal)
        assert forged not in REFUSAL_CLASS_SEMANTICS

        extended_classes = list(PowlRefusal) + [forged]

        def totality_holds(classes):
            documented = frozenset(REFUSAL_CLASS_SEMANTICS)
            return frozenset(classes) <= documented

        assert totality_holds(list(PowlRefusal)) is True
        assert totality_holds(extended_classes) is False

        # And the export refuses to mint a record for the unknown class —
        # no silent negation either.
        assert (
            refusal_to_negation_record(refusal=forged, subject="s", searched_at="t")
            is None
        )
