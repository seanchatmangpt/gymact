"""Manufacture heterogeneous execution ecologies without selecting among them.

A layered ecology is a compact graph representation of a Cartesian possibility space.
The number of graph nodes grows with the sum of alternatives while the number of
possible paths represents their product. This is the DCM substrate for planner,
provider, parameterization, effector, verifier and controller combinations.
"""
from __future__ import annotations

from typing import Any, Self

from pydantic import Field, model_validator

from gymact.action_contract import ReversalClass
from gymact.combinatorial import (
    DecisionPhase,
    Factor,
    MorphismKind,
    MorphismRequirements,
    ObjectiveVector,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
)
from gymact.evidence import digest
from gymact.models import FrozenModel, Standing


class EcologyAlternative(FrozenModel):
    alternative_id: str = Field(min_length=1)
    semantic_ref: str = Field(min_length=1)
    ontology_refs: tuple[str, ...] = ()
    standing: Standing = Standing.CANDIDATE
    evidence_refs: tuple[str, ...] = ()
    requirements: MorphismRequirements = Field(default_factory=MorphismRequirements)
    objectives: ObjectiveVector = Field(default_factory=ObjectiveVector)
    attributes: dict[str, Any] = Field(default_factory=dict)


class EcologyDimension(FrozenModel):
    dimension_id: str = Field(min_length=1)
    object_kind: PossibilityObjectKind
    morphism_kind: MorphismKind = MorphismKind.REALIZE
    phase: DecisionPhase = DecisionPhase.SELECT
    reversal: ReversalClass = ReversalClass.REVERSIBLE
    alternatives: tuple[EcologyAlternative, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def dimension_is_reversible_space(self) -> Self:
        if self.phase is DecisionPhase.DO:
            raise ValueError("ECOLOGY_DIMENSION_CANNOT_BE_DO")
        if self.reversal is not ReversalClass.REVERSIBLE:
            raise ValueError("ECOLOGY_DIMENSION_MUST_BE_PROVEN_REVERSIBLE")
        ids = [item.alternative_id for item in self.alternatives]
        if len(ids) != len(set(ids)):
            raise ValueError("DUPLICATE_ECOLOGY_ALTERNATIVE_ID")
        return self


class IrreversibleOption(FrozenModel):
    option_id: str = Field(min_length=1)
    target: PossibilityObject
    morphism_kind: MorphismKind = MorphismKind.ACTUATE
    reversal: ReversalClass = ReversalClass.IRREVERSIBLE
    standing: Standing = Standing.CANDIDATE
    evidence_refs: tuple[str, ...] = ()
    requirements: MorphismRequirements = Field(
        default_factory=lambda: MorphismRequirements(execution_grant_required=True)
    )
    objectives: ObjectiveVector = Field(default_factory=ObjectiveVector)

    @model_validator(mode="after")
    def irreversible_option_requires_grant(self) -> Self:
        if not self.requirements.execution_grant_required:
            raise ValueError("IRREVERSIBLE_OPTION_REQUIRES_EXECUTION_GRANT")
        if self.reversal is ReversalClass.REVERSIBLE:
            raise ValueError("IRREVERSIBLE_OPTION_CANNOT_DECLARE_REVERSIBLE")
        return self


class ManufacturedEcology(FrozenModel):
    graph: PossibilityGraph
    factors: tuple[Factor, ...]
    reversible_path_cardinality: int
    irreversible_choice_cardinality: int


def manufacture_ecology(
    *,
    start: PossibilityObject,
    dimensions: tuple[EcologyDimension, ...],
    irreversible: tuple[IrreversibleOption, ...] = (),
) -> ManufacturedEcology:
    """Build the maximal layered possibility topology without choosing a path."""
    dimension_ids = [item.dimension_id for item in dimensions]
    if len(dimension_ids) != len(set(dimension_ids)):
        raise ValueError("DUPLICATE_ECOLOGY_DIMENSION_ID")

    graph = PossibilityGraph(objects=(start,))
    previous_ids = (start.object_id,)
    factors: list[Factor] = []
    path_cardinality = 1

    for dimension in dimensions:
        factors.append(
            Factor(
                factor_id=dimension.dimension_id,
                alternatives=tuple(item.alternative_id for item in dimension.alternatives),
            )
        )
        path_cardinality *= len(dimension.alternatives)
        next_ids: list[str] = []
        for alternative in dimension.alternatives:
            object_id = f"{dimension.dimension_id}:{alternative.alternative_id}"
            graph = graph.with_object(
                PossibilityObject(
                    object_id=object_id,
                    kind=dimension.object_kind,
                    semantic_ref=alternative.semantic_ref,
                    ontology_refs=alternative.ontology_refs,
                    standing=alternative.standing,
                    evidence_refs=alternative.evidence_refs,
                    attributes=alternative.attributes,
                )
            )
            next_ids.append(object_id)
            for source_id in previous_ids:
                morphism_id = digest(
                    {
                        "dimension": dimension.dimension_id,
                        "source": source_id,
                        "target": object_id,
                    }
                )
                graph = graph.with_morphism(
                    PossibilityMorphism(
                        morphism_id=f"urn:gymact:morphism:{morphism_id}",
                        source_id=source_id,
                        target_id=object_id,
                        kind=dimension.morphism_kind,
                        phase=dimension.phase,
                        reversal=dimension.reversal,
                        requirements=alternative.requirements,
                        objectives=alternative.objectives,
                        standing=alternative.standing,
                        evidence_refs=alternative.evidence_refs,
                    )
                )
        previous_ids = tuple(next_ids)

    for option in irreversible:
        graph = graph.with_object(option.target)
        for source_id in previous_ids:
            morphism_id = digest(
                {
                    "irreversible_option": option.option_id,
                    "source": source_id,
                    "target": option.target.object_id,
                }
            )
            graph = graph.with_morphism(
                PossibilityMorphism(
                    morphism_id=f"urn:gymact:morphism:{morphism_id}",
                    source_id=source_id,
                    target_id=option.target.object_id,
                    kind=option.morphism_kind,
                    phase=DecisionPhase.DO,
                    reversal=option.reversal,
                    requirements=option.requirements,
                    objectives=option.objectives,
                    standing=option.standing,
                    evidence_refs=option.evidence_refs,
                )
            )

    return ManufacturedEcology(
        graph=graph,
        factors=tuple(factors),
        reversible_path_cardinality=path_cardinality,
        irreversible_choice_cardinality=path_cardinality * len(irreversible),
    )
