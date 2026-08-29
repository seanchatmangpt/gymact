from dataclasses import replace

import pytest

from gymact.dd_ui import (
    PresentationCandidate,
    deterministic_select,
    make_intent,
    make_screen_receipt,
    pareto_frontier,
    replay_matches,
)


def candidate(identity: str, *scores: int, actions: tuple[str, ...] = ()) -> PresentationCandidate:
    return PresentationCandidate(identity, tuple(scores), actions)


def test_pareto_frontier_is_order_invariant() -> None:
    weak = candidate("weak", 1, 1, 1, 1, 1, 1)
    strong = candidate("strong", 2, 2, 2, 2, 2, 2)
    tradeoff = candidate("tradeoff", 3, 0, 3, 0, 3, 0)
    assert pareto_frontier((weak, strong, tradeoff)) == pareto_frontier((tradeoff, weak, strong))
    assert {item.identity for item in pareto_frontier((weak, strong, tradeoff))} == {"strong", "tradeoff"}


def test_selection_is_deterministic_and_reversible() -> None:
    frontier = (
        candidate("a", 2, 2, 2, 2, 2, 2),
        candidate("b", 2, 2, 2, 2, 2, 2),
    )
    assert deterministic_select(frontier).identity == "b"


def test_screen_receipt_records_zero_irreversible_selection() -> None:
    frontier = (candidate("screen", 1, 1, 1, 1, 1, 1),)
    receipt = make_screen_receipt(
        grammar="dd-ui/2", world="world", input_payload="input", frontier=frontier, screen="screen"
    )
    assert receipt.irreversible_selections == 0


def test_rendered_action_manufactures_intent_without_actuation() -> None:
    projected = candidate("screen", 1, 1, 1, 1, 1, 1, actions=("approve",))
    receipt = make_screen_receipt(
        grammar="dd-ui/2", world="world", input_payload="input", frontier=(projected,), screen="screen"
    )
    intent = make_intent(receipt, "claim-1", "approve", projected.projected_actions)
    assert intent.actuation is False
    assert intent.screen_digest == receipt.screen_digest


def test_unprojected_action_is_refused() -> None:
    projected = candidate("screen", 1, 1, 1, 1, 1, 1, actions=("approve",))
    receipt = make_screen_receipt(
        grammar="dd-ui/2", world="world", input_payload="input", frontier=(projected,), screen="screen"
    )
    with pytest.raises(ValueError, match="REFUSED_UNPROJECTED_ACTION"):
        make_intent(receipt, "claim-1", "delete", projected.projected_actions)


def test_replay_rejects_tampered_world_digest() -> None:
    frontier = (candidate("screen", 1, 1, 1, 1, 1, 1),)
    receipt = make_screen_receipt(
        grammar="dd-ui/2", world="world", input_payload="input", frontier=frontier, screen="screen"
    )
    observed = {
        "grammar_digest": receipt.grammar_digest,
        "world_digest": "tampered",
        "input_digest": receipt.input_digest,
        "frontier_digest": receipt.frontier_digest,
        "screen_digest": receipt.screen_digest,
    }
    assert replay_matches(receipt, observed) is False
    assert replay_matches(replace(receipt, irreversible_selections=1), observed) is False
