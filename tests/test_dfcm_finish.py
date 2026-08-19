from __future__ import annotations

import pytest

from gymact.dfcm_finish import (
    CompletionAdmissionError,
    CompletionItem,
    CompletionMove,
    admit_completion_cut,
    manufacture_and_admit_completion,
    manufacture_completion_frontier,
    select_completion_cut,
)


def _move(
    item_id: str,
    move_id: str,
    *,
    kind: str = "CONSTRUCT",
    reversible: bool = True,
    cost: int = 1,
    requires_authority: bool = False,
) -> CompletionMove:
    return CompletionMove(
        move_id=move_id,
        item_id=item_id,
        kind=kind,
        reversible=reversible,
        cost=cost,
        requires_authority=requires_authority,
        evidence_refs=(f"urn:test:evidence:{move_id}",),
    )


def test_dfcm_preserves_full_reversible_cross_product_before_selection() -> None:
    items = (
        CompletionItem(
            item_id="registry",
            standing="BUILD_BROKEN",
            moves=(
                _move("registry", "adapt-registry", kind="ADAPT", cost=2),
                _move("registry", "compose-registry", kind="COMPOSE", cost=1),
            ),
        ),
        CompletionItem(
            item_id="mcp",
            standing="PARTIAL_ALIVE",
            moves=(
                _move("mcp", "repair-ontology", kind="CONSTRUCT", cost=1),
                _move("mcp", "repair-runtime", kind="CONSTRUCT", cost=3),
            ),
        ),
    )

    frontier = manufacture_completion_frontier(subject_ref="urn:test:head:abc", items=items)

    assert frontier.standing == "PARTIAL_ALIVE"
    assert frontier.total_cardinality == 4
    assert frontier.truncated is False
    assert len(frontier.plans) == 4
    assert frontier.plans[0].move_ids == ("compose-registry", "repair-ontology")
    assert len(frontier.frontier_digest_blake3) == 64

    cut = select_completion_cut(frontier)
    assert cut.selected is not None
    assert cut.selected.move_ids == ("compose-registry", "repair-ontology")
    assert cut.reason == "REVERSIBLE_CUT_SELECTED_CONSTRUCT_ONLY"
    assert len(cut.cut_digest_blake3) == 64
    assert admit_completion_cut(cut=cut, items=items) == cut


def test_unknown_or_authority_only_edges_are_blocked_not_promoted_to_do() -> None:
    items = (
        CompletionItem(
            item_id="production-do",
            standing="UNKNOWN",
            moves=(
                _move(
                    "production-do",
                    "actuate-prod",
                    kind="DO",
                    reversible=False,
                    requires_authority=True,
                ),
            ),
        ),
    )

    frontier, cut = manufacture_and_admit_completion(
        subject_ref="urn:test:head:def",
        items=items,
    )

    assert frontier.standing == "BLOCKED"
    assert frontier.blocked_items == ("production-do",)
    assert frontier.total_cardinality == 0
    assert cut.standing == "BLOCKED"
    assert cut.selected is None


def test_dependency_must_have_terminal_standing_before_child_enters_frontier() -> None:
    items = (
        CompletionItem(
            item_id="source",
            standing="PARTIAL_ALIVE",
            moves=(_move("source", "verify-source", kind="VERIFY"),),
        ),
        CompletionItem(
            item_id="projection",
            standing="BUILD_BROKEN",
            dependencies=("source",),
            moves=(_move("projection", "render-projection"),),
        ),
    )

    frontier = manufacture_completion_frontier(subject_ref="urn:test:head:ghi", items=items)

    assert frontier.blocked_items == ("projection",)
    assert frontier.total_cardinality == 1
    assert frontier.plans[0].move_ids == ("verify-source",)


def test_terminal_subject_is_alive_without_manufacturing_fake_work() -> None:
    items = (
        CompletionItem(item_id="tests", standing="ALIVE"),
        CompletionItem(item_id="unsupported-vendor", standing="UNSUPPORTED"),
        CompletionItem(item_id="forbidden-path", standing="REFUSED"),
    )

    frontier, cut = manufacture_and_admit_completion(subject_ref="urn:test:head:jkl", items=items)

    assert frontier.standing == "ALIVE"
    assert frontier.unresolved_items == ()
    assert frontier.plans == ()
    assert cut.standing == "ALIVE"
    assert cut.selected is None
    assert cut.reason == "SUBJECT_ALREADY_ALIVE"


def test_frontier_is_deterministic_and_bounded_without_losing_true_cardinality() -> None:
    items = tuple(
        CompletionItem(
            item_id=f"item-{index}",
            standing="PARTIAL_ALIVE",
            moves=(
                _move(f"item-{index}", f"a-{index}"),
                _move(f"item-{index}", f"b-{index}"),
            ),
        )
        for index in range(5)
    )

    first = manufacture_completion_frontier(
        subject_ref="urn:test:head:mno",
        items=items,
        max_plans=3,
    )
    second = manufacture_completion_frontier(
        subject_ref="urn:test:head:mno",
        items=items,
        max_plans=3,
    )

    assert first.total_cardinality == 32
    assert first.truncated is True
    assert len(first.plans) == 3
    assert first == second


def test_admission_refuses_tampered_cut_that_reintroduces_do() -> None:
    items = (
        CompletionItem(
            item_id="subject",
            standing="PARTIAL_ALIVE",
            moves=(
                _move("subject", "construct", kind="CONSTRUCT"),
                _move(
                    "subject",
                    "do",
                    kind="DO",
                    reversible=False,
                    requires_authority=True,
                ),
            ),
        ),
    )
    frontier = manufacture_completion_frontier(subject_ref="urn:test:head:pqr", items=items)
    cut = select_completion_cut(frontier)
    assert cut.selected is not None

    tampered_plan = cut.selected.model_copy(update={"move_ids": ("do",)})
    tampered_cut = cut.model_copy(update={"selected": tampered_plan})

    with pytest.raises(CompletionAdmissionError, match="REFUSED:DO_REQUIRES_BRCE"):
        admit_completion_cut(cut=tampered_cut, items=items)


def test_invalid_graph_edges_are_typed_refusals() -> None:
    with pytest.raises(ValueError, match="UNKNOWN_COMPLETION_DEPENDENCY"):
        manufacture_completion_frontier(
            subject_ref="urn:test:head:stu",
            items=(
                CompletionItem(
                    item_id="projection",
                    standing="UNKNOWN",
                    dependencies=("missing",),
                    moves=(_move("projection", "inspect", kind="INSPECT"),),
                ),
            ),
        )

    with pytest.raises(ValueError, match="MOVE_ITEM_MISMATCH"):
        manufacture_completion_frontier(
            subject_ref="urn:test:head:vwx",
            items=(
                CompletionItem(
                    item_id="one",
                    standing="UNKNOWN",
                    moves=(_move("other", "bad"),),
                ),
            ),
        )
