from __future__ import annotations

import pytest

from gymact.action_contract import ReversalClass
from gymact.combinatorial import (
    AdmissionContext,
    DecisionPhase,
    ExplorationBounds,
    Factor,
    MorphismKind,
    MorphismRequirements,
    ObjectiveVector,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
    explore_maximal_reversible,
    manufacture_combination_space,
    pareto_paths,
)
from gymact.models import Standing


def node(object_id: str, kind: PossibilityObjectKind) -> PossibilityObject:
    return PossibilityObject(
        object_id=object_id,
        kind=kind,
        semantic_ref=f"urn:test:{object_id}",
    )


def edge(
    morphism_id: str,
    source_id: str,
    target_id: str,
    *,
    phase: DecisionPhase = DecisionPhase.CONSTRUCT,
    capability_refs: tuple[str, ...] = (),
    policy_refs: tuple[str, ...] = (),
    required_revision: str | None = None,
    objectives: ObjectiveVector | None = None,
) -> PossibilityMorphism:
    return PossibilityMorphism(
        morphism_id=morphism_id,
        source_id=source_id,
        target_id=target_id,
        kind=MorphismKind.ACTUATE if phase is DecisionPhase.DO else MorphismKind.REALIZE,
        phase=phase,
        reversal=(
            ReversalClass.IRREVERSIBLE
            if phase is DecisionPhase.DO
            else ReversalClass.REVERSIBLE
        ),
        requirements=MorphismRequirements(
            capability_refs=capability_refs,
            policy_refs=policy_refs,
            required_revision=required_revision,
            execution_grant_required=phase is DecisionPhase.DO,
        ),
        objectives=objectives or ObjectiveVector(),
    )


def test_union_is_lossless_idempotent_and_rejects_identity_aliasing() -> None:
    left = PossibilityGraph(objects=(node("subject", PossibilityObjectKind.SUBJECT),))
    provider = node("provider", PossibilityObjectKind.PROVIDER)
    right = PossibilityGraph(objects=(provider,))
    combined = left.union(right, right)
    assert {item.object_id for item in combined.objects} == {"subject", "provider"}

    conflicting = PossibilityGraph(
        objects=(
            PossibilityObject(
                object_id="provider",
                kind=PossibilityObjectKind.PLANNER,
                semantic_ref="urn:test:different",
            ),
        )
    )
    with pytest.raises(ValueError, match="POSSIBILITY_OBJECT_IDENTITY_CONFLICT"):
        combined.union(conflicting)


def test_failed_edge_is_topology_not_graph_failure() -> None:
    graph = PossibilityGraph(
        objects=(
            node("o", PossibilityObjectKind.ADMITTED_OBSERVATION),
            node("p1", PossibilityObjectKind.PROVIDER),
            node("p2", PossibilityObjectKind.PROVIDER),
            node("a1", PossibilityObjectKind.ACTION),
            node("a2", PossibilityObjectKind.ACTION),
        ),
        morphisms=(
            edge("o-p1", "o", "p1", capability_refs=("cap:missing",)),
            edge("o-p2", "o", "p2"),
            edge("p1-a1", "p1", "a1"),
            edge("p2-a2", "p2", "a2"),
        ),
    )
    result = explore_maximal_reversible(graph, start_ids=("o",))
    assert any(item.reason == "REQUIRED_CAPABILITY_UNAVAILABLE" for item in result.evaluations)
    assert any(path.object_ids[-1] == "a2" for path in result.paths)
    assert not any(path.object_ids[-1] == "a1" for path in result.paths)
    assert result.graph_digest == graph.graph_digest


def test_all_reversible_branches_are_preserved_until_do_cut() -> None:
    graph = PossibilityGraph(
        objects=(
            node("o", PossibilityObjectKind.ADMITTED_OBSERVATION),
            node("planner-a", PossibilityObjectKind.PLANNER),
            node("planner-b", PossibilityObjectKind.PLANNER),
            node("plan-a", PossibilityObjectKind.PLAN),
            node("plan-b", PossibilityObjectKind.PLAN),
            node("effect-a", PossibilityObjectKind.RECEIPT),
            node("effect-b", PossibilityObjectKind.RECEIPT),
        ),
        morphisms=(
            edge("select-a", "o", "planner-a"),
            edge("select-b", "o", "planner-b"),
            edge("plan-a", "planner-a", "plan-a"),
            edge("plan-b", "planner-b", "plan-b"),
            edge("do-a", "plan-a", "effect-a", phase=DecisionPhase.DO),
            edge("do-b", "plan-b", "effect-b", phase=DecisionPhase.DO),
        ),
    )
    result = explore_maximal_reversible(
        graph,
        start_ids=("o",),
        context=AdmissionContext(execution_grant_ref="urn:grant:present"),
    )
    terminals = {path.object_ids[-1] for path in result.paths}
    assert {"plan-a", "plan-b"} <= terminals
    assert "effect-a" not in terminals and "effect-b" not in terminals
    assert {item.morphism_id for item in result.irreversible_frontier} == {"do-a", "do-b"}
    assert all(item.admitted for item in result.irreversible_frontier)


def test_revision_and_policy_fences_preserve_other_choices() -> None:
    graph = PossibilityGraph(
        objects=(
            node("o", PossibilityObjectKind.ADMITTED_OBSERVATION),
            node("stale", PossibilityObjectKind.PLAN),
            node("policy", PossibilityObjectKind.PLAN),
            node("open", PossibilityObjectKind.PLAN),
        ),
        morphisms=(
            edge("stale-edge", "o", "stale", required_revision="rev-1"),
            edge("policy-edge", "o", "policy", policy_refs=("policy:required",)),
            edge("open-edge", "o", "open"),
        ),
    )
    result = explore_maximal_reversible(
        graph,
        start_ids=("o",),
        context=AdmissionContext(current_revision="rev-2"),
    )
    reasons = {item.reason for item in result.evaluations}
    assert "REVISION_MISMATCH" in reasons
    assert "POLICY_NOT_ADMITTED" in reasons
    assert any(path.object_ids[-1] == "open" for path in result.paths)


def test_explicit_bounds_report_truncation_instead_of_silent_pruning() -> None:
    graph = PossibilityGraph(
        objects=(
            node("o", PossibilityObjectKind.ADMITTED_OBSERVATION),
            node("a", PossibilityObjectKind.ACTION),
            node("b", PossibilityObjectKind.ACTION),
            node("c", PossibilityObjectKind.ACTION),
        ),
        morphisms=(
            edge("o-a", "o", "a"),
            edge("o-b", "o", "b"),
            edge("o-c", "o", "c"),
        ),
    )
    result = explore_maximal_reversible(
        graph,
        start_ids=("o",),
        bounds=ExplorationBounds(max_paths=2),
    )
    assert result.truncated
    assert "MAX_PATHS" in result.truncation_reasons
    assert len(result.paths) == 2


def test_objective_bounds_are_fences_not_rankers() -> None:
    graph = PossibilityGraph(
        objects=(
            node("o", PossibilityObjectKind.ADMITTED_OBSERVATION),
            node("cheap", PossibilityObjectKind.PLAN),
            node("expensive", PossibilityObjectKind.PLAN),
        ),
        morphisms=(
            edge(
                "cheap-edge",
                "o",
                "cheap",
                objectives=ObjectiveVector(monetary_cost=1.0),
            ),
            edge(
                "expensive-edge",
                "o",
                "expensive",
                objectives=ObjectiveVector(monetary_cost=11.0),
            ),
        ),
    )
    result = explore_maximal_reversible(
        graph,
        start_ids=("o",),
        bounds=ExplorationBounds(max_monetary_cost=10.0),
    )
    assert any(path.object_ids[-1] == "cheap" for path in result.paths)
    assert not any(path.object_ids[-1] == "expensive" for path in result.paths)
    assert any(item.reason == "EXPLORATION_BOUND_EXCEEDED" for item in result.evaluations)


def test_pareto_frontier_preserves_incomparable_paths() -> None:
    fast = ObjectiveVector(monetary_cost=10.0, wall_time_s=1.0, expected_value=10.0)
    cheap = ObjectiveVector(monetary_cost=1.0, wall_time_s=10.0, expected_value=10.0)
    dominated = ObjectiveVector(monetary_cost=12.0, wall_time_s=12.0, expected_value=9.0)
    from gymact.combinatorial import PossibilityPath

    paths = (
        PossibilityPath(object_ids=("o", "fast"), objectives=fast),
        PossibilityPath(object_ids=("o", "cheap"), objectives=cheap),
        PossibilityPath(object_ids=("o", "dominated"), objectives=dominated),
    )
    frontier = pareto_paths(paths)
    assert {item.object_ids[-1] for item in frontier} == {"fast", "cheap"}


def test_factor_product_manufactures_cartesian_space_without_choosing() -> None:
    space = manufacture_combination_space(
        (
            Factor(factor_id="planner", alternatives=("p1", "p2", "p3")),
            Factor(factor_id="provider", alternatives=("e1", "e2")),
            Factor(factor_id="verifier", alternatives=("v1", "v2")),
        )
    )
    assert space.total_cardinality == 12
    assert len(space.combinations) == 12
    assert not space.truncated
    assert len({item.combination_id for item in space.combinations}) == 12


def test_factor_product_explicitly_reports_cardinality_truncation() -> None:
    space = manufacture_combination_space(
        (
            Factor(factor_id="planner", alternatives=("p1", "p2", "p3")),
            Factor(factor_id="provider", alternatives=("e1", "e2")),
        ),
        bounds=ExplorationBounds(max_combinations=4),
    )
    assert space.total_cardinality == 6
    assert len(space.combinations) == 4
    assert space.truncated


def test_graph_cannot_smuggle_live_execution_authority() -> None:
    with pytest.raises(ValueError, match="POSSIBILITY_GRAPH_CANNOT_CARRY_EXECUTION_AUTHORITY"):
        PossibilityObject(
            object_id="bad",
            kind=PossibilityObjectKind.ACTION,
            semantic_ref="urn:test:bad",
            attributes={"execution_grant": {"principal": "urn:user"}},
        )

    with pytest.raises(ValueError, match="POSSIBILITY_GRAPH_CANNOT_CARRY_EXECUTION_AUTHORITY"):
        PossibilityMorphism(
            morphism_id="bad-edge",
            source_id="a",
            target_id="b",
            kind=MorphismKind.REALIZE,
            phase=DecisionPhase.CONSTRUCT,
            attributes={"nested": {"authority_ref": "urn:authority"}},
        )


def test_do_cannot_be_declared_without_execution_grant_requirement() -> None:
    with pytest.raises(ValueError, match="DO_MORPHISM_REQUIRES_EXECUTION_GRANT"):
        PossibilityMorphism(
            morphism_id="unsafe-do",
            source_id="a",
            target_id="b",
            kind=MorphismKind.ACTUATE,
            phase=DecisionPhase.DO,
        )
