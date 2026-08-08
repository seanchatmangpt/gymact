"""Experimental Crown primitives for GymAct provider selection, projections, and self-play.

This module is deliberately powerless: it manufactures descriptions, indexes evidence,
and proposes candidates. It never receives or exercises execution authority.
"""

from __future__ import annotations

import json
import re
from enum import StrEnum
from typing import Any, Iterable, Self

from pydantic import Field, model_validator

from gymact.action_contract import ActionDefinition, ObservationConfidence, SubjectRef
from gymact.models import FrozenModel, Standing


class ProviderFamily(StrEnum):
    FILESYSTEM = "filesystem"
    GIT = "git"
    GITHUB = "github"
    DATABASE = "database"
    BROWSER = "browser"
    KUBERNETES = "kubernetes"
    CLOUD = "cloud"
    INFRASTRUCTURE_AS_CODE = "infrastructure_as_code"
    MCP = "mcp"
    A2A = "a2a"
    BPMN = "bpmn"
    ROBOTICS = "robotics"
    INDUSTRIAL_OT = "industrial_ot"
    BENCHMARK = "benchmark"
    SIMULATION = "simulation"
    ENTERPRISE_SAAS = "enterprise_saas"


class ProblemSignature(FrozenModel):
    deterministic: bool
    fully_observable: bool
    discrete: bool
    finite_horizon: bool
    temporal: bool = False
    concurrent: bool = False
    adversarial: bool = False
    cooperative: bool = False
    multi_agent: bool = False
    resource_constrained: bool = False
    numeric: bool = False
    probabilistic: bool = False
    reversible: bool = True
    safety_constrained: bool = True
    uncertainty_class: str = "none"
    effect_latency_class: str = "bounded"
    observation_latency_class: str = "bounded"

    def key(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


class TransitionMetrics(FrozenModel):
    wall_time_s: float = Field(ge=0.0)
    monetary_cost: float = Field(ge=0.0)
    memory_bytes: int = Field(default=0, ge=0)
    quality: float = Field(default=1.0, ge=0.0)
    failure_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    human_interventions: int = Field(default=0, ge=0)
    model_tokens: int = Field(default=0, ge=0)
    verification_confidence: ObservationConfidence = ObservationConfidence.SAME_PROVIDER_OBSERVED


_CONFIDENCE_RANK = {
    ObservationConfidence.SELF_REPORTED: 0,
    ObservationConfidence.SAME_PROVIDER_OBSERVED: 1,
    ObservationConfidence.INDEPENDENT_CHANNEL: 2,
    ObservationConfidence.MULTI_ORACLE: 3,
    ObservationConfidence.PHYSICAL_SENSOR: 4,
}


class ProviderBenchmarkRecord(FrozenModel):
    action_ref: str = Field(min_length=1)
    provider_ref: str = Field(min_length=1)
    signature: ProblemSignature
    objective: str = "verified_consequence"
    environment: str = "unspecified"
    hardware: str = "unspecified"
    metrics: TransitionMetrics
    result: Standing
    receipt_ref: str = Field(min_length=1)


def _dominates(left: ProviderBenchmarkRecord, right: ProviderBenchmarkRecord) -> bool:
    """Return True when left is no worse on all objectives and better on at least one."""
    l = left.metrics
    r = right.metrics
    no_worse = (
        l.wall_time_s <= r.wall_time_s
        and l.monetary_cost <= r.monetary_cost
        and l.memory_bytes <= r.memory_bytes
        and l.failure_probability <= r.failure_probability
        and l.human_interventions <= r.human_interventions
        and l.model_tokens <= r.model_tokens
        and l.quality >= r.quality
        and _CONFIDENCE_RANK[l.verification_confidence]
        >= _CONFIDENCE_RANK[r.verification_confidence]
    )
    strictly_better = (
        l.wall_time_s < r.wall_time_s
        or l.monetary_cost < r.monetary_cost
        or l.memory_bytes < r.memory_bytes
        or l.failure_probability < r.failure_probability
        or l.human_interventions < r.human_interventions
        or l.model_tokens < r.model_tokens
        or l.quality > r.quality
        or _CONFIDENCE_RANK[l.verification_confidence]
        > _CONFIDENCE_RANK[r.verification_confidence]
    )
    return no_worse and strictly_better


def pareto_frontier(records: Iterable[ProviderBenchmarkRecord]) -> tuple[ProviderBenchmarkRecord, ...]:
    candidates = tuple(records)
    return tuple(
        candidate
        for candidate in candidates
        if not any(
            other is not candidate and _dominates(other, candidate)
            for other in candidates
        )
    )


class EmpiricalProviderIndex:
    """Receipt-backed retrieval index. It ranks only already-applicable evidence."""

    def __init__(self) -> None:
        self._records: list[ProviderBenchmarkRecord] = []

    def record(self, value: ProviderBenchmarkRecord) -> None:
        self._records.append(value)

    def query(
        self,
        *,
        action_ref: str,
        signature: ProblemSignature,
        environment: str | None = None,
        objective: str = "verified_consequence",
    ) -> tuple[ProviderBenchmarkRecord, ...]:
        eligible = (
            item
            for item in self._records
            if item.action_ref == action_ref
            and item.signature == signature
            and item.objective == objective
            and item.result in {Standing.ALIVE, Standing.ADOPTED}
            and (environment is None or item.environment == environment)
        )
        return pareto_frontier(eligible)


class CapabilityCacheEntry(FrozenModel):
    problem_identity: str = Field(min_length=1)
    environment_identity: str = Field(min_length=1)
    action_ref: str = Field(min_length=1)
    provider_ref: str = Field(min_length=1)
    evidence_refs: tuple[str, ...]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def forbid_cached_authority(self) -> Self:
        forbidden = {"authority_ref", "principal", "delegated_principal", "execution_grant"}
        leaked = forbidden.intersection(self.metadata)
        if leaked:
            raise ValueError(f"CAPABILITY_CACHE_AUTHORITY_LEAK:{sorted(leaked)}")
        return self


class CapabilityCache:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], CapabilityCacheEntry] = {}

    def put(self, entry: CapabilityCacheEntry) -> None:
        self._entries[(entry.problem_identity, entry.environment_identity)] = entry

    def get(self, problem_identity: str, environment_identity: str) -> CapabilityCacheEntry | None:
        return self._entries.get((problem_identity, environment_identity))


class ProjectionKind(StrEnum):
    PDDL = "pddl"
    PPDDL = "ppddl"
    RDDL = "rddl"
    POWL_V2 = "powl_v2"
    BPMN = "bpmn"
    A2A = "a2a"


class ActionProjection(FrozenModel):
    kind: ProjectionKind
    action_ref: str
    capability_ref: str
    payload: dict[str, Any]
    authority_transferred: bool = False

    @model_validator(mode="after")
    def authority_must_remain_external(self) -> Self:
        if self.authority_transferred:
            raise ValueError("PROJECTION_CANNOT_TRANSFER_AUTHORITY")
        return self


def _symbol(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return normalized or "gymact-action"


def project_action(action: ActionDefinition, kind: ProjectionKind) -> ActionProjection:
    """Project one powerless semantic action into planner/process/transport data."""
    name = _symbol(action.semantic_id)
    preconditions = tuple(_symbol(value) for value in action.preconditions)
    effects = tuple(_symbol(value.predicate) for value in action.expected_effects)
    common = {
        "name": name,
        "semantic_id": action.semantic_id,
        "preconditions": preconditions,
        "effects": effects,
        "input_schema": action.input_schema,
        "cost": action.cost.model_dump(mode="json"),
        "locality": action.locality.model_dump(mode="json"),
    }
    if kind in {ProjectionKind.PDDL, ProjectionKind.PPDDL, ProjectionKind.RDDL}:
        payload = {**common, "planner_dialect": kind.value}
    elif kind is ProjectionKind.POWL_V2:
        payload = {**common, "node_type": "activity", "partial_order": True}
    elif kind is ProjectionKind.BPMN:
        payload = {**common, "element": "serviceTask", "implementation": "gymact-intent"}
    elif kind is ProjectionKind.A2A:
        payload = {
            **common,
            "message_type": "gymact.intent.candidate",
            "authorization": None,
        }
    else:  # pragma: no cover - closed enum, defensive against unsafe casting
        raise ValueError(f"UNSUPPORTED_PROJECTION:{kind}")
    return ActionProjection(
        kind=kind,
        action_ref=action.semantic_id,
        capability_ref=action.capability_ref,
        payload=payload,
    )


class SelfPlayKind(StrEnum):
    VALID = "valid"
    STALE_REVISION = "stale_revision"
    MISSING_AUTHORITY = "missing_authority"
    WRONG_CAPABILITY = "wrong_capability"
    AMBIGUOUS_SUBJECT = "ambiguous_subject"
    LOST_ACK = "lost_ack"
    PARTIAL_EFFECT = "partial_effect"
    WRONG_EFFECT = "wrong_effect"
    DELAYED_EFFECT = "delayed_effect"
    DUPLICATE_REQUEST = "duplicate_request"
    REPLAY_MISMATCH = "replay_mismatch"


class SelfPlayScenario(FrozenModel):
    kind: SelfPlayKind
    action_ref: str
    subject: SubjectRef
    mutation: dict[str, Any]
    expected_disposition: str


def manufacture_self_play(
    action: ActionDefinition, subject: SubjectRef
) -> tuple[SelfPlayScenario, ...]:
    dispositions = {
        SelfPlayKind.VALID: "VERIFY",
        SelfPlayKind.STALE_REVISION: "REVISION_MISMATCH_REFUSED",
        SelfPlayKind.MISSING_AUTHORITY: "AUTHORITY_REFUSED",
        SelfPlayKind.WRONG_CAPABILITY: "CAPABILITY_REFUSED",
        SelfPlayKind.AMBIGUOUS_SUBJECT: "AMBIGUOUS_SUBJECT_REFUSED",
        SelfPlayKind.LOST_ACK: "UNCERTAIN",
        SelfPlayKind.PARTIAL_EFFECT: "UNCERTAIN",
        SelfPlayKind.WRONG_EFFECT: "VERIFICATION_REFUSED",
        SelfPlayKind.DELAYED_EFFECT: "RECONCILE",
        SelfPlayKind.DUPLICATE_REQUEST: "IDEMPOTENCY_CHECK",
        SelfPlayKind.REPLAY_MISMATCH: "REPLAY_REFUSED",
    }
    return tuple(
        SelfPlayScenario(
            kind=kind,
            action_ref=action.semantic_id,
            subject=subject,
            mutation={"scenario": kind.value},
            expected_disposition=disposition,
        )
        for kind, disposition in dispositions.items()
    )


class DifferentialVerdict(FrozenModel):
    agrees: bool
    oracle_digests: tuple[str, ...]
    standing: Standing


def differential_verdict(*digests: str) -> DifferentialVerdict:
    if len(digests) < 2:
        raise ValueError("DIFFERENTIAL_VERIFICATION_REQUIRES_MULTIPLE_ORACLES")
    agrees = len(set(digests)) == 1
    return DifferentialVerdict(
        agrees=agrees,
        oracle_digests=tuple(digests),
        standing=Standing.ALIVE if agrees else Standing.UNCERTAIN,
    )


class ForwardBenchSubject(FrozenModel):
    canonical_id: str = Field(min_length=1)
    pinned_revision: str = Field(min_length=1)
    provenance_ref: str = Field(min_length=1)
    ontology_ref: str = Field(min_length=1)
    capability_refs: tuple[str, ...]
    environment_ref: str = Field(min_length=1)
    expected_evidence: tuple[str, ...]
    applicable_planners: tuple[str, ...] = ()
    applicable_gyms: tuple[str, ...] = ()
    scenarios: tuple[str, ...] = ()
    standing: Standing = Standing.UNKNOWN


class VCTObservation(FrozenModel):
    verified_transitions: int = Field(ge=0)
    wall_time_s: float = Field(gt=0.0)
    monetary_cost: float = Field(gt=0.0)
    human_intervention_factor: float = Field(gt=0.0)
    hot_transitions: int = Field(default=0, ge=0)
    warm_transitions: int = Field(default=0, ge=0)
    total_transitions: int = Field(gt=0)
    frontier_model_tokens: int = Field(default=0, ge=0)

    @property
    def vct(self) -> float:
        return self.verified_transitions / (
            self.wall_time_s * self.monetary_cost * self.human_intervention_factor
        )

    @property
    def rho(self) -> float:
        return (self.hot_transitions + self.warm_transitions) / self.total_transitions

    @property
    def kappa(self) -> float | None:
        if self.frontier_model_tokens == 0:
            return None
        return self.verified_transitions / self.frontier_model_tokens


class CostPoint(FrozenModel):
    repetitions: int = Field(gt=0)
    frontier_agent_cost: float = Field(ge=0.0)
    gymact_cost: float = Field(ge=0.0)


class CrossoverResult(FrozenModel):
    observed: bool
    repetitions: int | None = None
    points: tuple[CostPoint, ...]


def find_crossover(points: Iterable[CostPoint]) -> CrossoverResult:
    ordered = tuple(sorted(points, key=lambda point: point.repetitions))
    for point in ordered:
        if point.gymact_cost < point.frontier_agent_cost:
            return CrossoverResult(observed=True, repetitions=point.repetitions, points=ordered)
    return CrossoverResult(observed=False, points=ordered)


class EdgeControllerManifest(FrozenModel):
    controller_id: str = Field(min_length=1)
    action_refs: tuple[str, ...]
    authority_policy_refs: tuple[str, ...]
    verifier_refs: tuple[str, ...]
    execution_mode: str = "wasm"
    content_digest: str = Field(min_length=1)
    standing: Standing = Standing.STRUCTURAL
