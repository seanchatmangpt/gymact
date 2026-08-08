from __future__ import annotations

import pytest

from gymact.action_contract import (
    ActionDefinition,
    ExecutionGrant,
    ExpectedEffect,
    ReversalClass,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
    construct_prepared_action,
)
from gymact.authority import AllowListAuthorityResolver
from gymact.combinatorial import (
    AdmissionContext,
    DecisionPhase,
    MorphismKind,
    MorphismRequirements,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
)
from gymact.cut import (
    CombinatorialBRCEBroker,
    manufacture_broker_request,
    select_irreversible_cut,
)
from gymact.maximal import explore_combinatorial_maximum
from gymact.models import MaterializationIntent, Standing
from gymact.providers import MemoryProvider
from gymact.runtime import ProductionGymAct

AUTHORITY = "urn:test:authority"
CAPABILITY = "urn:gymact:memory:capability:set"


@pytest.mark.asyncio
async def test_real_consequence_receipt_binds_graph_path_and_irreversible_cut() -> None:
    runtime = ProductionGymAct(
        authority_resolver=AllowListAuthorityResolver({AUTHORITY})
    )
    runtime.register_provider(MemoryProvider())
    materialized = await runtime.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"x": 1}, "requires_authority": True},
            idempotency_key="dcm-materialize",
        )
    )
    assert materialized.episode is not None
    assert materialized.observation is not None
    episode = materialized.episode
    observation = materialized.observation

    effect = ExpectedEffect(predicate="state", parameters={"x": 2})
    action = ActionDefinition(
        semantic_id="urn:action:set-x",
        provider_ref="urn:provider:memory",
        capability_ref=CAPABILITY,
        subject_type="schema:Thing",
        input_schema={"type": "object"},
        expected_effects=(effect,),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:observer:memory",
            expected={"x": 2},
        ),
        reversal=ReversalClass.IRREVERSIBLE,
    )
    subject = SubjectRef(
        semantic_id="urn:subject:memory",
        provider_ref=episode.environment_id,
    )
    prepared = construct_prepared_action(
        action,
        episode_id=episode.episode_id,
        subject=subject,
        payload={"key": "x", "value": 2},
        admission_digest=observation.state_digest,
        idempotency_key="dcm-set-x",
    )
    grant = ExecutionGrant(
        principal="urn:principal:test",
        action_ref=action.semantic_id,
        subject=subject,
        capability_ref=CAPABILITY,
        authority_ref=AUTHORITY,
        policy_revision="policy-1",
        admitted_observation_ref=observation.state_digest,
        intended_effects=(effect,),
        nonce="dcm-nonce",
    )
    graph = PossibilityGraph(
        objects=(
            PossibilityObject(
                object_id="o-star",
                kind=PossibilityObjectKind.ADMITTED_OBSERVATION,
                semantic_ref="urn:observation:admitted",
            ),
            PossibilityObject(
                object_id="plan",
                kind=PossibilityObjectKind.PLAN,
                semantic_ref="urn:plan:set-x",
            ),
            PossibilityObject(
                object_id="verified-effect",
                kind=PossibilityObjectKind.RECEIPT,
                semantic_ref="urn:effect:set-x",
            ),
        ),
        morphisms=(
            PossibilityMorphism(
                morphism_id="construct-plan",
                source_id="o-star",
                target_id="plan",
                kind=MorphismKind.PLAN,
                phase=DecisionPhase.CONSTRUCT,
                reversal=ReversalClass.REVERSIBLE,
            ),
            PossibilityMorphism(
                morphism_id="actuate-set-x",
                source_id="plan",
                target_id="verified-effect",
                kind=MorphismKind.ACTUATE,
                phase=DecisionPhase.DO,
                reversal=ReversalClass.IRREVERSIBLE,
                requirements=MorphismRequirements(execution_grant_required=True),
            ),
        ),
    )
    exploration = explore_combinatorial_maximum(
        graph,
        start_ids=("o-star",),
        context=AdmissionContext(execution_grant_ref="urn:grant:admitted"),
    )
    frontier = exploration.irreversible_frontier[0]
    basis_ref = f"urn:gymact:receipt:{materialized.receipt.receipt_id}"
    selection = select_irreversible_cut(
        graph,
        exploration,
        path_id=frontier.path_id,
        morphism_id=frontier.morphism_id,
        action=action,
        prepared=prepared,
        grant=grant,
        selector_ref="urn:selector:dcm",
        basis_refs=(basis_ref,),
    )
    request = manufacture_broker_request(
        selection,
        action=action,
        prepared=prepared,
        grant=grant,
        expected={"x": 2},
    )
    transition = await CombinatorialBRCEBroker(runtime).execute(request)

    assert transition.standing is Standing.ALIVE
    assert transition.receipt.verified is True
    assert transition.receipt.possibility_graph_digest == graph.graph_digest
    assert transition.receipt.possibility_exploration_digest == selection.exploration_digest
    assert transition.receipt.possibility_path_id == frontier.path_id
    assert transition.receipt.possibility_morphism_id == frontier.morphism_id
    assert transition.receipt.selection_digest == selection.selection_digest
    assert transition.receipt.selection_basis_refs == (basis_ref,)
    assert transition.receipt.parent_receipt_ids
    assert (await runtime.observe(episode.episode_id)).state == {"x": 2}
