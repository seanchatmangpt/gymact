from __future__ import annotations

from gymact.combinatorial import (
    AdmissionContext,
    DecisionPhase,
    MorphismKind,
    MorphismRequirements,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
    explore_maximal_reversible,
)
from gymact.compileout_graph import (
    GraphRecipeIdentity,
    admit_graph_recipe,
    compile_graph_recipe,
)
from gymact.models import Standing


def graph() -> PossibilityGraph:
    return PossibilityGraph(
        objects=(
            PossibilityObject(
                object_id="o",
                kind=PossibilityObjectKind.ADMITTED_OBSERVATION,
                semantic_ref="urn:o",
            ),
            PossibilityObject(
                object_id="plan",
                kind=PossibilityObjectKind.PLAN,
                semantic_ref="urn:plan",
            ),
            PossibilityObject(
                object_id="effect",
                kind=PossibilityObjectKind.RECEIPT,
                semantic_ref="urn:effect",
            ),
        ),
        morphisms=(
            PossibilityMorphism(
                morphism_id="construct",
                source_id="o",
                target_id="plan",
                kind=MorphismKind.PLAN,
                phase=DecisionPhase.CONSTRUCT,
            ),
            PossibilityMorphism(
                morphism_id="do",
                source_id="plan",
                target_id="effect",
                kind=MorphismKind.ACTUATE,
                phase=DecisionPhase.DO,
                requirements=MorphismRequirements(execution_grant_required=True),
            ),
        ),
    )


def test_hot_recipe_reuses_graph_route_not_authority() -> None:
    topology = graph()
    exploration = explore_maximal_reversible(topology, start_ids=("o",))
    path = next(item for item in exploration.paths if item.object_ids[-1] == "plan")
    identity = GraphRecipeIdentity(
        problem_identity="problem-1",
        environment_identity="env-1",
        authority_class="operator",
        policy_revision="policy-1",
        verifier_ref="verifier-1",
        input_contract_digest="input-1",
        graph_digest=topology.graph_digest,
    )
    recipe = compile_graph_recipe(
        identity,
        exploration,
        path_id=path.path_id,
        irreversible_morphism_id="do",
        source_receipt_refs=("receipt-1", "receipt-2"),
    )
    assert not hasattr(recipe, "execution_grant")
    admitted = admit_graph_recipe(recipe, identity, exploration)
    assert admitted.admitted
    assert admitted.model_required is False
    assert admitted.standing is Standing.CANDIDATE
    assert admitted.reason == "HOT_GRAPH_ROUTE_ADMITTED_AUTHORITY_STILL_REQUIRED"


def test_hot_recipe_invalidates_on_graph_or_route_drift() -> None:
    topology = graph()
    exploration = explore_maximal_reversible(topology, start_ids=("o",))
    path = next(item for item in exploration.paths if item.object_ids[-1] == "plan")
    identity = GraphRecipeIdentity(
        problem_identity="problem-1",
        environment_identity="env-1",
        authority_class="operator",
        policy_revision="policy-1",
        verifier_ref="verifier-1",
        input_contract_digest="input-1",
        graph_digest=topology.graph_digest,
    )
    recipe = compile_graph_recipe(
        identity,
        exploration,
        path_id=path.path_id,
        irreversible_morphism_id="do",
        source_receipt_refs=("receipt-1",),
    )
    drifted_identity = identity.model_copy(update={"policy_revision": "policy-2"})
    stale = admit_graph_recipe(recipe, drifted_identity, exploration)
    assert stale.standing is Standing.STALE
    assert stale.model_required

    changed = topology.with_object(
        PossibilityObject(
            object_id="extra",
            kind=PossibilityObjectKind.PLAN,
            semantic_ref="urn:extra",
        )
    )
    changed_exploration = explore_maximal_reversible(changed, start_ids=("o",))
    stale_graph = admit_graph_recipe(recipe, identity, changed_exploration)
    assert stale_graph.standing is Standing.STALE
    assert stale_graph.reason == "COMPILED_GRAPH_RECIPE_GRAPH_DRIFT"


def test_hot_recipe_does_not_require_do_to_be_authority_admitted_during_compilation() -> None:
    topology = graph()
    exploration = explore_maximal_reversible(
        topology,
        start_ids=("o",),
        context=AdmissionContext(),
    )
    frontier = exploration.irreversible_frontier[0]
    assert frontier.admitted is False
    path = next(item for item in exploration.paths if item.path_id == frontier.path_id)
    identity = GraphRecipeIdentity(
        problem_identity="problem-1",
        environment_identity="env-1",
        authority_class="operator",
        policy_revision="policy-1",
        verifier_ref="verifier-1",
        input_contract_digest="input-1",
        graph_digest=topology.graph_digest,
    )
    recipe = compile_graph_recipe(
        identity,
        exploration,
        path_id=path.path_id,
        irreversible_morphism_id=frontier.morphism_id,
        source_receipt_refs=("prior-success-receipt",),
    )
    admitted = admit_graph_recipe(recipe, identity, exploration)
    assert admitted.admitted
    assert admitted.standing is Standing.CANDIDATE
