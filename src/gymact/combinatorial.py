"""Design for Combinatorial Maximum (DCM) primitives.

The canonical object in this module is a powerless possibility graph. It preserves
lawful alternatives and their typed morphisms until an irreversible DO boundary
forces an explicit authority-bound selection.

The graph is deliberately incapable of actuation. It contains semantic identities,
requirements, evidence, costs, reversibility and topology only. ExecutionGrant is
never stored here; BRCE remains the exclusive DO path.
"""
from __future__ import annotations

import math
from enum import StrEnum
from itertools import islice, product
from typing import Any, Iterable, Self

from pydantic import Field, model_validator

from gymact.action_contract import ReversalClass
from gymact.evidence import digest
from gymact.models import FrozenModel, Standing


class PossibilityObjectKind(StrEnum):
    OBSERVATION = "observation"
    ADMITTED_OBSERVATION = "admitted_observation"
    SUBJECT = "subject"
    CAPABILITY = "capability"
    ACTION = "action"
    PLAN = "plan"
    PROVIDER = "provider"
    PLANNER = "planner"
    VERIFIER = "verifier"
    POLICY = "policy"
    CONTROLLER = "controller"
    PROCESS = "process"
    RECEIPT = "receipt"


class MorphismKind(StrEnum):
    OBSERVE = "observe"
    ADMIT = "admit"
    ENABLE = "enable"
    REALIZE = "realize"
    PLAN = "plan"
    PROJECT = "project"
    MANUFACTURE = "manufacture"
    VERIFY = "verify"
    COMPENSATE = "compensate"
    REVERSE = "reverse"
    ACTUATE = "actuate"
    REPLAY = "replay"
    REUSE = "reuse"


class DecisionPhase(StrEnum):
    """Authority partition: SELECT and CONSTRUCT are powerless; DO is consequential."""

    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    DO = "DO"


class PossibilityObject(FrozenModel):
    object_id: str = Field(min_length=1)
    kind: PossibilityObjectKind
    semantic_ref: str = Field(min_length=1)
    revision: str | None = None
    ontology_refs: tuple[str, ...] = ()
    standing: Standing = Standing.UNKNOWN
    evidence_refs: tuple[str, ...] = ()
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def graph_objects_cannot_carry_live_authority(self) -> Self:
        _forbid_authority_payload(self.attributes)
        return self


class ObjectiveVector(FrozenModel):
    """Composable objectives. Lower is better except confidence/value."""

    monetary_cost: float = Field(default=0.0, ge=0.0)
    wall_time_s: float = Field(default=0.0, ge=0.0)
    compute_units: float = Field(default=0.0, ge=0.0)
    human_interventions: float = Field(default=0.0, ge=0.0)
    risk_score: float = Field(default=0.0, ge=0.0)
    verification_confidence: int = Field(default=4, ge=0, le=4)
    expected_value: float = Field(default=0.0)

    def compose(self, other: ObjectiveVector) -> ObjectiveVector:
        """Sequential composition: additive costs/risk, bottleneck confidence."""
        return ObjectiveVector(
            monetary_cost=self.monetary_cost + other.monetary_cost,
            wall_time_s=self.wall_time_s + other.wall_time_s,
            compute_units=self.compute_units + other.compute_units,
            human_interventions=self.human_interventions + other.human_interventions,
            risk_score=self.risk_score + other.risk_score,
            verification_confidence=min(
                self.verification_confidence,
                other.verification_confidence,
            ),
            expected_value=self.expected_value + other.expected_value,
        )


class MorphismRequirements(FrozenModel):
    capability_refs: tuple[str, ...] = ()
    policy_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    required_revision: str | None = None
    execution_grant_required: bool = False


class PossibilityMorphism(FrozenModel):
    morphism_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    kind: MorphismKind
    phase: DecisionPhase
    reversal: ReversalClass = ReversalClass.UNKNOWN
    requirements: MorphismRequirements = Field(default_factory=MorphismRequirements)
    objectives: ObjectiveVector = Field(default_factory=ObjectiveVector)
    standing: Standing = Standing.CANDIDATE
    evidence_refs: tuple[str, ...] = ()
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_do_boundary_and_powerlessness(self) -> Self:
        _forbid_authority_payload(self.attributes)
        if self.kind is MorphismKind.ACTUATE and self.phase is not DecisionPhase.DO:
            raise ValueError("ACTUATION_MORPHISM_MUST_BE_DO")
        if self.phase is DecisionPhase.DO and not self.requirements.execution_grant_required:
            raise ValueError("DO_MORPHISM_REQUIRES_EXECUTION_GRANT")
        if self.phase is not DecisionPhase.DO and self.requirements.execution_grant_required:
            raise ValueError("NON_DO_MORPHISM_CANNOT_REQUIRE_EXECUTION_GRANT")
        return self


class PossibilityGraph(FrozenModel):
    """Immutable compositional graph; methods return new graphs rather than mutate."""

    objects: tuple[PossibilityObject, ...] = ()
    morphisms: tuple[PossibilityMorphism, ...] = ()

    @model_validator(mode="after")
    def validate_topology(self) -> Self:
        object_ids = [item.object_id for item in self.objects]
        morphism_ids = [item.morphism_id for item in self.morphisms]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("DUPLICATE_POSSIBILITY_OBJECT_ID")
        if len(morphism_ids) != len(set(morphism_ids)):
            raise ValueError("DUPLICATE_POSSIBILITY_MORPHISM_ID")
        known = set(object_ids)
        for edge in self.morphisms:
            if edge.source_id not in known or edge.target_id not in known:
                raise ValueError("MORPHISM_ENDPOINT_NOT_IN_GRAPH")
        return self

    @property
    def graph_digest(self) -> str:
        return digest(self.model_dump(mode="json"))

    def object(self, object_id: str) -> PossibilityObject:
        for item in self.objects:
            if item.object_id == object_id:
                return item
        raise KeyError(object_id)

    def outgoing(self, object_id: str) -> tuple[PossibilityMorphism, ...]:
        return tuple(item for item in self.morphisms if item.source_id == object_id)

    def with_object(self, value: PossibilityObject) -> PossibilityGraph:
        existing = {item.object_id: item for item in self.objects}
        prior = existing.get(value.object_id)
        if prior is not None and prior != value:
            raise ValueError("POSSIBILITY_OBJECT_IDENTITY_CONFLICT")
        if prior is not None:
            return self
        return self.model_copy(update={"objects": (*self.objects, value)})

    def with_morphism(self, value: PossibilityMorphism) -> PossibilityGraph:
        existing = {item.morphism_id: item for item in self.morphisms}
        prior = existing.get(value.morphism_id)
        if prior is not None and prior != value:
            raise ValueError("POSSIBILITY_MORPHISM_IDENTITY_CONFLICT")
        if prior is not None:
            return self
        return self.model_copy(update={"morphisms": (*self.morphisms, value)})

    def union(self, *others: PossibilityGraph) -> PossibilityGraph:
        """Combinatorial union is lossless and rejects identity aliasing."""
        result = self
        for other in others:
            for node in other.objects:
                result = result.with_object(node)
            for edge in other.morphisms:
                result = result.with_morphism(edge)
        return result


class ExplorationBounds(FrozenModel):
    """Explicit bounds prevent combinatorial explosion from becoming silent pruning."""

    max_depth: int = Field(default=16, ge=0)
    max_paths: int = Field(default=4096, ge=1)
    max_combinations: int = Field(default=10000, ge=1)
    max_monetary_cost: float | None = Field(default=None, ge=0.0)
    max_wall_time_s: float | None = Field(default=None, ge=0.0)
    max_compute_units: float | None = Field(default=None, ge=0.0)
    max_human_interventions: float | None = Field(default=None, ge=0.0)
    max_risk_score: float | None = Field(default=None, ge=0.0)


class AdmissionContext(FrozenModel):
    """Current admitted facts. A grant is referenced, never embedded in the graph."""

    capability_refs: tuple[str, ...] = ()
    policy_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    current_revision: str | None = None
    execution_grant_ref: str | None = None


class MorphismEvaluation(FrozenModel):
    morphism_id: str
    standing: Standing
    admitted: bool
    reason: str


class PossibilityPath(FrozenModel):
    object_ids: tuple[str, ...]
    morphism_ids: tuple[str, ...] = ()
    objectives: ObjectiveVector = Field(default_factory=ObjectiveVector)

    @property
    def path_id(self) -> str:
        return digest(self.model_dump(mode="json"))


class IrreversibleFrontierEdge(FrozenModel):
    path_id: str
    morphism_id: str
    target_id: str
    standing: Standing
    admitted: bool
    reason: str


class ExplorationResult(FrozenModel):
    graph_digest: str
    start_ids: tuple[str, ...]
    paths: tuple[PossibilityPath, ...]
    pareto_path_ids: tuple[str, ...]
    irreversible_frontier: tuple[IrreversibleFrontierEdge, ...]
    evaluations: tuple[MorphismEvaluation, ...]
    truncated: bool
    truncation_reasons: tuple[str, ...] = ()


class Factor(FrozenModel):
    """One independent reversible choice dimension in D x Pi x Theta x E x V ..."""

    factor_id: str = Field(min_length=1)
    alternatives: tuple[str, ...] = Field(min_length=1)


class Combination(FrozenModel):
    assignments: dict[str, str]

    @property
    def combination_id(self) -> str:
        return digest(self.model_dump(mode="json"))


class CombinationSpace(FrozenModel):
    factors: tuple[Factor, ...]
    total_cardinality: int
    combinations: tuple[Combination, ...]
    truncated: bool


_FORBIDDEN_AUTHORITY_KEYS = {
    "execution_grant",
    "executiongrant",
    "grant",
    "principal",
    "delegated_principal",
    "nonce",
    "authority_ref",
}


def _forbid_authority_payload(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_AUTHORITY_KEYS:
                raise ValueError("POSSIBILITY_GRAPH_CANNOT_CARRY_EXECUTION_AUTHORITY")
            _forbid_authority_payload(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _forbid_authority_payload(nested)


def _within_bounds(value: ObjectiveVector, bounds: ExplorationBounds) -> bool:
    checks = (
        (value.monetary_cost, bounds.max_monetary_cost),
        (value.wall_time_s, bounds.max_wall_time_s),
        (value.compute_units, bounds.max_compute_units),
        (value.human_interventions, bounds.max_human_interventions),
        (value.risk_score, bounds.max_risk_score),
    )
    return all(limit is None or observed <= limit for observed, limit in checks)


def evaluate_morphism(
    morphism: PossibilityMorphism,
    context: AdmissionContext,
) -> MorphismEvaluation:
    """Evaluate one edge without deleting it from the possibility topology."""
    if morphism.standing in {
        Standing.BLOCKED,
        Standing.UNSUPPORTED,
        Standing.REFUSED,
        Standing.STALE,
    }:
        return MorphismEvaluation(
            morphism_id=morphism.morphism_id,
            standing=morphism.standing,
            admitted=False,
            reason=f"EDGE_STANDING_{morphism.standing.value}",
        )
    required = morphism.requirements
    if not set(required.capability_refs).issubset(context.capability_refs):
        return MorphismEvaluation(
            morphism_id=morphism.morphism_id,
            standing=Standing.UNSUPPORTED,
            admitted=False,
            reason="REQUIRED_CAPABILITY_UNAVAILABLE",
        )
    if not set(required.policy_refs).issubset(context.policy_refs):
        return MorphismEvaluation(
            morphism_id=morphism.morphism_id,
            standing=Standing.REFUSED,
            admitted=False,
            reason="POLICY_NOT_ADMITTED",
        )
    if not set(required.evidence_refs).issubset(context.evidence_refs):
        return MorphismEvaluation(
            morphism_id=morphism.morphism_id,
            standing=Standing.BLOCKED,
            admitted=False,
            reason="REQUIRED_EVIDENCE_MISSING",
        )
    if (
        required.required_revision is not None
        and context.current_revision != required.required_revision
    ):
        return MorphismEvaluation(
            morphism_id=morphism.morphism_id,
            standing=Standing.STALE,
            admitted=False,
            reason="REVISION_MISMATCH",
        )
    if required.execution_grant_required and context.execution_grant_ref is None:
        return MorphismEvaluation(
            morphism_id=morphism.morphism_id,
            standing=Standing.CANDIDATE,
            admitted=False,
            reason="EXECUTION_GRANT_REQUIRED",
        )
    return MorphismEvaluation(
        morphism_id=morphism.morphism_id,
        standing=Standing.CANDIDATE,
        admitted=True,
        reason="LAWFUL_EDGE_ADMITTED",
    )


def _dominates(left: PossibilityPath, right: PossibilityPath) -> bool:
    l = left.objectives
    r = right.objectives
    no_worse = (
        l.monetary_cost <= r.monetary_cost
        and l.wall_time_s <= r.wall_time_s
        and l.compute_units <= r.compute_units
        and l.human_interventions <= r.human_interventions
        and l.risk_score <= r.risk_score
        and l.verification_confidence >= r.verification_confidence
        and l.expected_value >= r.expected_value
    )
    better = (
        l.monetary_cost < r.monetary_cost
        or l.wall_time_s < r.wall_time_s
        or l.compute_units < r.compute_units
        or l.human_interventions < r.human_interventions
        or l.risk_score < r.risk_score
        or l.verification_confidence > r.verification_confidence
        or l.expected_value > r.expected_value
    )
    return no_worse and better


def pareto_paths(paths: Iterable[PossibilityPath]) -> tuple[PossibilityPath, ...]:
    """Return the whole non-dominated frontier; never manufacture one best path."""
    values = tuple(paths)
    return tuple(
        candidate
        for candidate in values
        if not any(other is not candidate and _dominates(other, candidate) for other in values)
    )


def explore_maximal_reversible(
    graph: PossibilityGraph,
    *,
    start_ids: Iterable[str],
    context: AdmissionContext | None = None,
    bounds: ExplorationBounds | None = None,
) -> ExplorationResult:
    """Enumerate the bounded reversible closure and stop at every DO cut.

    A refused/blocked/unsupported edge remains an evaluation in the result. It does
    not invalidate siblings, ancestors or the graph. DO edges are never traversed;
    they form the explicit irreversible frontier even when a grant reference exists.
    """
    ctx = context or AdmissionContext()
    limits = bounds or ExplorationBounds()
    starts = tuple(start_ids)
    for object_id in starts:
        graph.object(object_id)

    stack = [PossibilityPath(object_ids=(object_id,)) for object_id in reversed(starts)]
    emitted: list[PossibilityPath] = []
    frontier: list[IrreversibleFrontierEdge] = []
    evaluations: list[MorphismEvaluation] = []
    truncation_reasons: set[str] = set()

    while stack:
        path = stack.pop()
        depth = len(path.morphism_ids)
        outgoing = graph.outgoing(path.object_ids[-1])
        if depth >= limits.max_depth:
            if outgoing:
                truncation_reasons.add("MAX_DEPTH")
            continue

        for edge in outgoing:
            evaluation = evaluate_morphism(edge, ctx)
            evaluations.append(evaluation)
            if edge.phase is DecisionPhase.DO:
                frontier.append(
                    IrreversibleFrontierEdge(
                        path_id=path.path_id,
                        morphism_id=edge.morphism_id,
                        target_id=edge.target_id,
                        standing=evaluation.standing,
                        admitted=evaluation.admitted,
                        reason=evaluation.reason,
                    )
                )
                continue
            if not evaluation.admitted:
                continue
            objectives = path.objectives.compose(edge.objectives)
            if not _within_bounds(objectives, limits):
                evaluations.append(
                    MorphismEvaluation(
                        morphism_id=edge.morphism_id,
                        standing=Standing.BLOCKED,
                        admitted=False,
                        reason="EXPLORATION_BOUND_EXCEEDED",
                    )
                )
                continue
            next_path = PossibilityPath(
                object_ids=(*path.object_ids, edge.target_id),
                morphism_ids=(*path.morphism_ids, edge.morphism_id),
                objectives=objectives,
            )
            if len(emitted) >= limits.max_paths:
                truncation_reasons.add("MAX_PATHS")
                stack.clear()
                break
            emitted.append(next_path)
            stack.append(next_path)

    pareto = pareto_paths(emitted)
    return ExplorationResult(
        graph_digest=graph.graph_digest,
        start_ids=starts,
        paths=tuple(emitted),
        pareto_path_ids=tuple(path.path_id for path in pareto),
        irreversible_frontier=tuple(frontier),
        evaluations=tuple(evaluations),
        truncated=bool(truncation_reasons),
        truncation_reasons=tuple(sorted(truncation_reasons)),
    )


def manufacture_combination_space(
    factors: Iterable[Factor],
    *,
    bounds: ExplorationBounds | None = None,
) -> CombinationSpace:
    """Materialize D x Pi x Theta x E x V style possibility space without choosing."""
    dimensions = tuple(factors)
    limits = bounds or ExplorationBounds()
    ids = [item.factor_id for item in dimensions]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_FACTOR_ID")
    total = math.prod(len(item.alternatives) for item in dimensions) if dimensions else 1
    tuples = product(*(item.alternatives for item in dimensions))
    values = tuple(
        Combination(assignments=dict(zip(ids, choices, strict=True)))
        for choices in islice(tuples, limits.max_combinations)
    )
    return CombinationSpace(
        factors=dimensions,
        total_cardinality=total,
        combinations=values,
        truncated=len(values) < total,
    )
