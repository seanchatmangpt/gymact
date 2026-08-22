from __future__ import annotations

from gymact.commerce_dfcm_graph import commerce_dfcm_frontier, commerce_possibility_graph
from gymact.combinatorial import DecisionPhase


def test_commerce_possibility_graph_preserves_all_semantics_without_authority() -> None:
    graph = commerce_possibility_graph()

    assert len(graph.objects) == 33
    assert len(graph.morphisms) == 32
    assert len({item.object_id for item in graph.objects}) == 33
    assert len({item.morphism_id for item in graph.morphisms}) == 32
    assert all("authority_ref" not in item.attributes for item in graph.objects)
    assert all("authority_ref" not in item.attributes for item in graph.morphisms)


def test_maximal_reversible_exploration_stops_at_all_do_edges() -> None:
    frontier = commerce_dfcm_frontier()

    assert frontier.semantic_capability_count == 32
    assert frontier.reversible_capability_count == 20
    assert frontier.do_frontier_count == 12
    assert frontier.bounded_internal_do_count == 5
    assert frontier.external_do_count == 7
    assert len(frontier.exploration.paths) == 20
    assert len(frontier.exploration.irreversible_frontier) == 12
    assert not frontier.exploration.truncated

    assert set(frontier.bounded_internal_do_bindings) == {
        "agreement.amend",
        "agreement.cancel",
        "agreement.renew",
        "entitlement.apply-event",
        "entitlement.lifecycle",
    }
    assert set(frontier.external_do_bindings) == {
        "external.banking",
        "external.eula",
        "external.kyc",
        "external.provider-review",
        "external.seller-registration",
        "external.tax",
        "meter.submit",
    }
    assert all(
        edge.phase is DecisionPhase.DO
        for edge in commerce_possibility_graph().morphisms
        if edge.attributes["binding"] in frontier.external_do_bindings
    )
    assert all(
        item.reason == "EXECUTION_GRANT_REQUIRED"
        for item in frontier.exploration.irreversible_frontier
    )
