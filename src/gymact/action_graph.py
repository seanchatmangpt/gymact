"""Project ActionDefinition into the canonical combinatorial possibility topology."""
from __future__ import annotations

from gymact.action_contract import (
    ActionDefinition,
    ObservationConfidence,
    ReversalClass,
    SubjectRef,
)
from gymact.combinatorial import (
    DecisionPhase,
    MorphismKind,
    MorphismRequirements,
    ObjectiveVector,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
)
from gymact.evidence import digest

_CONFIDENCE = {
    ObservationConfidence.SELF_REPORTED: 0,
    ObservationConfidence.SAME_PROVIDER_OBSERVED: 1,
    ObservationConfidence.INDEPENDENT_CHANNEL: 2,
    ObservationConfidence.MULTI_ORACLE: 3,
    ObservationConfidence.PHYSICAL_SENSOR: 4,
}


def _object_id(prefix: str, semantic_ref: str) -> str:
    return f"{prefix}:{digest(semantic_ref)}"


def _edge_id(source_id: str, target_id: str, *, action_ref: str | None = None) -> str:
    payload = {"from": source_id, "to": target_id, "action": action_ref}
    return f"urn:gymact:morphism:{digest(payload)}"


def action_possibility_fragment(
    action: ActionDefinition,
    subject: SubjectRef,
) -> PossibilityGraph:
    """Manufacture one powerless action path; union fragments to preserve alternatives."""
    subject_object = PossibilityObject(
        object_id=_object_id("subject", subject.semantic_id),
        kind=PossibilityObjectKind.SUBJECT,
        semantic_ref=subject.semantic_id,
        revision=subject.revision,
        attributes={"provider_ref": subject.provider_ref},
    )
    provider = PossibilityObject(
        object_id=_object_id("provider", action.provider_ref),
        kind=PossibilityObjectKind.PROVIDER,
        semantic_ref=action.provider_ref,
    )
    capability = PossibilityObject(
        object_id=_object_id("capability", action.capability_ref),
        kind=PossibilityObjectKind.CAPABILITY,
        semantic_ref=action.capability_ref,
    )
    action_object = PossibilityObject(
        object_id=_object_id("action", action.semantic_id),
        kind=PossibilityObjectKind.ACTION,
        semantic_ref=action.semantic_id,
        standing=action.standing,
        evidence_refs=action.evidence_refs,
        attributes={
            "subject_type": action.subject_type,
            "input_schema": action.input_schema,
            "output_schema": action.output_schema,
            "preconditions": action.preconditions,
            "locality": action.locality.model_dump(mode="json"),
        },
    )
    verifier = PossibilityObject(
        object_id=_object_id("verifier", action.verification.observer_ref),
        kind=PossibilityObjectKind.VERIFIER,
        semantic_ref=action.verification.observer_ref,
    )
    effects = [item.model_dump(mode="json") for item in action.expected_effects]
    effect_ref = f"urn:gymact:expected-effect:{digest(effects)}"
    effect = PossibilityObject(
        object_id=_object_id("effect", effect_ref),
        kind=PossibilityObjectKind.RECEIPT,
        semantic_ref=effect_ref,
    )

    reversible = ReversalClass.REVERSIBLE
    objectives = ObjectiveVector(
        monetary_cost=action.cost.monetary,
        wall_time_s=action.cost.expected_wall_time_s,
        compute_units=action.cost.compute_units,
        human_interventions=action.cost.expected_human_approvals,
        risk_score=action.cost.expected_failure_probability,
        verification_confidence=_CONFIDENCE[action.verification.minimum_confidence],
    )
    requirements = MorphismRequirements(
        capability_refs=(action.capability_ref, *action.authority.capability_refs),
        policy_refs=action.authority.policy_refs,
        required_revision=subject.revision,
        execution_grant_required=True,
    )
    edges = (
        PossibilityMorphism(
            morphism_id=_edge_id(subject_object.object_id, provider.object_id),
            source_id=subject_object.object_id,
            target_id=provider.object_id,
            kind=MorphismKind.ENABLE,
            phase=DecisionPhase.SELECT,
            reversal=reversible,
        ),
        PossibilityMorphism(
            morphism_id=_edge_id(provider.object_id, capability.object_id),
            source_id=provider.object_id,
            target_id=capability.object_id,
            kind=MorphismKind.ENABLE,
            phase=DecisionPhase.SELECT,
            reversal=reversible,
        ),
        PossibilityMorphism(
            morphism_id=_edge_id(capability.object_id, action_object.object_id),
            source_id=capability.object_id,
            target_id=action_object.object_id,
            kind=MorphismKind.REALIZE,
            phase=DecisionPhase.CONSTRUCT,
            reversal=reversible,
        ),
        PossibilityMorphism(
            morphism_id=_edge_id(action_object.object_id, verifier.object_id),
            source_id=action_object.object_id,
            target_id=verifier.object_id,
            kind=MorphismKind.VERIFY,
            phase=DecisionPhase.CONSTRUCT,
            reversal=reversible,
        ),
        PossibilityMorphism(
            morphism_id=_edge_id(
                verifier.object_id,
                effect.object_id,
                action_ref=action.semantic_id,
            ),
            source_id=verifier.object_id,
            target_id=effect.object_id,
            kind=MorphismKind.ACTUATE,
            phase=DecisionPhase.DO,
            reversal=action.reversal,
            requirements=requirements,
            objectives=objectives,
            standing=action.standing,
            evidence_refs=action.evidence_refs,
        ),
    )
    return PossibilityGraph(
        objects=(subject_object, provider, capability, action_object, verifier, effect),
        morphisms=edges,
    )
