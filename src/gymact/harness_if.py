"""Harness-IF evaluation profile for GymAct.

Implements Huang et al., "Harness-IF: Evaluating Instruction Following Across
Instruction Surfaces in Coding Agents", arXiv:2608.11727 (2026).

This is an evaluation/admission layer, not a GymAct provider. It never actuates
a world and grants no execution authority. It consumes execution evidence from
existing runs and derives rule-level verdicts, prior strata, cohort metrics,
cascade audits, deterministic replay, and the paper's separate E0 surface-
precedence analysis.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from hashlib import sha256
import json
import math
import random
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

PAPER_IRI = "https://arxiv.org/abs/2608.11727"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)


class Surface(StrEnum):
    HARNESS_DEFAULT = "HD"
    SYSTEM_PROMPT = "SP"
    TOOL_DESCRIPTION = "TD"
    SKILL_DESCRIPTION = "SD"
    PROJECT_FILE = "PF"
    USER_INSTRUCTION = "UI"


CONFIGURABLE_SURFACES = frozenset(
    {
        Surface.SYSTEM_PROMPT,
        Surface.TOOL_DESCRIPTION,
        Surface.SKILL_DESCRIPTION,
        Surface.PROJECT_FILE,
        Surface.USER_INSTRUCTION,
    }
)


class RuleFamily(StrEnum):
    PROFESSIONAL_WRITING = "professional-writing"
    OUTPUT_CONTROL = "output-control"
    CODE_STYLE = "code-style"
    WORKFLOW = "workflow"
    QUANTITATIVE = "quantitative"
    CONDITIONAL_LOGIC = "conditional-logic"
    TOOL_USE = "tool-use"


class Modality(StrEnum):
    REQUIRE = "require"
    FORBID = "forbid"
    CONDITIONAL_REQUIRE = "conditional-require"
    LIMIT_MAX = "limit-max"
    LIMIT_MIN = "limit-min"
    PREFER = "prefer"
    ALLOW = "allow"


class Prior(StrEnum):
    ALIGN = "align-prior"
    AGAINST = "against-prior"
    NEUTRAL = "neutral"


class PriorLineage(StrEnum):
    ZERO_INJECTION = "zero-injection"
    CURATED = "curated"
    UNKNOWN = "unknown"


class Observability(StrEnum):
    SURFACE = "surface"
    STRUCTURAL = "structural"
    BEHAVIORAL = "behavioral"
    DEEP = "deep"


class Verifiability(StrEnum):
    DETERMINISTIC = "deterministic"
    RUBRIC = "rubric"
    SUBJECTIVE = "subjective"


class Universality(StrEnum):
    UNIVERSAL = "universal"
    CROSS_CODING = "cross-coding"
    CROSS_NON_CODING = "cross-non-coding"
    SPECIFIC = "specific"


class SurfaceFit(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ScoringMethod(StrEnum):
    REGEX = "regex"
    AST = "ast"
    CROSS_FILE = "cross-file"
    COMMAND_OUTPUT = "command-output"
    HYBRID = "hybrid"
    LLM_JUDGE = "llm-judge"


class Severity(StrEnum):
    MUST = "must"
    SHOULD = "should"
    MAY = "may"

    @property
    def weight(self) -> int:
        return {Severity.MUST: 3, Severity.SHOULD: 2, Severity.MAY: 1}[self]


class VerdictStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NO_OPPORTUNITY = "no-opportunity"
    PARTIAL = "partial"

    @property
    def eligible(self) -> bool:
        return self in (VerdictStatus.PASS, VerdictStatus.FAIL)


class FailureClass(StrEnum):
    SHORTFALL = "shortfall"
    OVERSTEP = "overstep"
    PREFERENCE = "preference"


class Constraint(FrozenModel):
    """One atomic, independently judgeable Harness-IF rule."""

    rule_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    family: RuleFamily
    modality: Modality
    prior: Prior
    prior_lineage: PriorLineage = PriorLineage.UNKNOWN
    observability: Observability
    verifiability: Verifiability
    universality: Universality
    scoring_method: ScoringMethod
    severity: Severity = Severity.MUST
    surface_fit: Mapping[Surface, SurfaceFit]
    surface_variants: Mapping[Surface, str]
    depends_on: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_surface_contract(self) -> "Constraint":
        if Surface.HARNESS_DEFAULT in self.surface_variants:
            raise ValueError("HARNESS_IF_HD_IS_FIXED_NOT_CONFIGURABLE")
        for surface, rendering in self.surface_variants.items():
            if surface not in CONFIGURABLE_SURFACES:
                raise ValueError("HARNESS_IF_INVALID_CONFIGURABLE_SURFACE")
            if not rendering.strip():
                raise ValueError("HARNESS_IF_EMPTY_SURFACE_RENDERING")
            if self.surface_fit.get(surface, SurfaceFit.NONE) == SurfaceFit.NONE:
                raise ValueError("HARNESS_IF_VARIANT_ON_INADMISSIBLE_SURFACE")
        if not any(
            self.surface_fit.get(surface, SurfaceFit.NONE) != SurfaceFit.NONE
            for surface in CONFIGURABLE_SURFACES
        ):
            raise ValueError("HARNESS_IF_RULE_HAS_NO_ADMISSIBLE_SURFACE")
        if self.rule_id in self.depends_on:
            raise ValueError("HARNESS_IF_RULE_CANNOT_DEPEND_ON_ITSELF")
        return self

    def admits(self, surface: Surface) -> bool:
        return (
            surface in CONFIGURABLE_SURFACES
            and self.surface_fit.get(surface, SurfaceFit.NONE) != SurfaceFit.NONE
            and surface in self.surface_variants
        )


class ConstraintPlacement(FrozenModel):
    rule_id: str
    surface: Surface
    rendered_text: str


class Scenario(FrozenModel):
    scenario_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    task: str = Field(min_length=1)
    fixture_ref: str = Field(min_length=1)
    test_refs: tuple[str, ...] = ()


class BenchmarkItem(FrozenModel):
    item_id: str = Field(min_length=1)
    scenario: Scenario
    user_turns: tuple[str, ...]
    placements: tuple[ConstraintPlacement, ...]

    @model_validator(mode="after")
    def unique_rules(self) -> "BenchmarkItem":
        ids = [placement.rule_id for placement in self.placements]
        if len(ids) != len(set(ids)):
            raise ValueError("HARNESS_IF_RULE_PLACED_MORE_THAN_ONCE")
        if not self.user_turns:
            raise ValueError("HARNESS_IF_ITEM_REQUIRES_USER_TURN")
        return self


class PanelAdmission(FrozenModel):
    accepted: bool
    reason: str
    rule_count: int
    scorable_count: int


def place_constraint(constraint: Constraint, surface: Surface) -> ConstraintPlacement:
    """Place a rule on exactly one admissible configurable surface."""
    if surface == Surface.HARNESS_DEFAULT:
        raise ValueError("HARNESS_IF_HD_IS_FIXED_NOT_CONFIGURABLE")
    if not constraint.admits(surface):
        raise ValueError(
            f"HARNESS_IF_INADMISSIBLE_SURFACE:{constraint.rule_id}:{surface.value}"
        )
    return ConstraintPlacement(
        rule_id=constraint.rule_id,
        surface=surface,
        rendered_text=constraint.surface_variants[surface],
    )


def admit_panel_item(
    item: BenchmarkItem,
    library: Mapping[str, Constraint],
    *,
    min_rules: int = 25,
    max_rules: int = 35,
    min_scorable: int = 10,
    max_scorable: int = 27,
) -> PanelAdmission:
    """Apply the paper's frozen-panel item cardinality and placement gates."""
    missing = sorted({p.rule_id for p in item.placements} - set(library))
    if missing:
        return PanelAdmission(
            accepted=False,
            reason=f"UNKNOWN_RULES:{','.join(missing)}",
            rule_count=len(item.placements),
            scorable_count=0,
        )
    for placement in item.placements:
        if not library[placement.rule_id].admits(placement.surface):
            return PanelAdmission(
                accepted=False,
                reason=(
                    f"INADMISSIBLE_SURFACE:{placement.rule_id}:"
                    f"{placement.surface.value}"
                ),
                rule_count=len(item.placements),
                scorable_count=0,
            )
    count = len(item.placements)
    if not min_rules <= count <= max_rules:
        return PanelAdmission(
            accepted=False,
            reason="RULE_PACK_OUT_OF_RANGE",
            rule_count=count,
            scorable_count=0,
        )
    scorable = sum(
        library[p.rule_id].verifiability != Verifiability.SUBJECTIVE
        for p in item.placements
    )
    if not min_scorable <= scorable <= max_scorable:
        return PanelAdmission(
            accepted=False,
            reason="SCORABLE_PACK_OUT_OF_RANGE",
            rule_count=count,
            scorable_count=scorable,
        )
    return PanelAdmission(
        accepted=True,
        reason="ADMITTED",
        rule_count=count,
        scorable_count=scorable,
    )


class ExecutionEvidence(FrozenModel):
    """Evidence consumed by rule checkers; evidence grants no execution authority."""

    final_output: str = ""
    files: Mapping[str, str] = Field(default_factory=dict)
    command_outputs: Mapping[str, str] = Field(default_factory=dict)
    trace_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    log_refs: tuple[str, ...] = ()
    state_before: Mapping[str, Any] = Field(default_factory=dict)
    state_after: Mapping[str, Any] = Field(default_factory=dict)


class RuleAssessment(FrozenModel):
    status: VerdictStatus
    reason: str
    evidence_refs: tuple[str, ...] = ()


@runtime_checkable
class RuleChecker(Protocol):
    def __call__(
        self,
        constraint: Constraint,
        placement: ConstraintPlacement,
        evidence: ExecutionEvidence,
    ) -> RuleAssessment: ...


class JudgeVote(FrozenModel):
    judge_id: str
    status: VerdictStatus
    reason: str = ""


def majority_vote(votes: Sequence[JudgeVote]) -> RuleAssessment:
    """Paper-faithful three-vote majority for LLM-judge and hybrid checks."""
    if len(votes) != 3:
        raise ValueError("HARNESS_IF_JUDGE_REQUIRES_THREE_VOTES")
    binary = [
        vote.status
        for vote in votes
        if vote.status in (VerdictStatus.PASS, VerdictStatus.FAIL)
    ]
    if len(binary) < 2:
        return RuleAssessment(
            status=VerdictStatus.PARTIAL,
            reason="NO_BINARY_MAJORITY",
        )
    status, count = Counter(binary).most_common(1)[0]
    if count < 2:
        return RuleAssessment(
            status=VerdictStatus.PARTIAL,
            reason="NO_BINARY_MAJORITY",
        )
    return RuleAssessment(
        status=status,
        reason="THREE_VOTE_MAJORITY",
        evidence_refs=tuple(vote.judge_id for vote in votes),
    )


class RuleVerdict(FrozenModel):
    agent_id: str
    item_id: str
    round_id: int = Field(ge=0)
    rule_id: str
    surface: Surface
    status: VerdictStatus
    method: ScoringMethod
    reason: str = ""
    evidence_refs: tuple[str, ...] = ()
    cascade_id: str | None = None
    missing_artifact_ref: str | None = None

    @property
    def observation_key(self) -> tuple[str, int, str]:
        return (self.item_id, self.round_id, self.rule_id)

    @property
    def eligible(self) -> bool:
        return self.status.eligible

    @property
    def z(self) -> int:
        if not self.eligible:
            raise ValueError("HARNESS_IF_NON_BINARY_VERDICT_HAS_NO_Z")
        return int(self.status == VerdictStatus.PASS)


def evaluate_rule(
    *,
    agent_id: str,
    item_id: str,
    round_id: int,
    constraint: Constraint,
    placement: ConstraintPlacement,
    evidence: ExecutionEvidence,
    checker: RuleChecker,
    cascade_id: str | None = None,
    missing_artifact_ref: str | None = None,
) -> RuleVerdict:
    """Evaluate F(x,y,s) through an injected checker without granting DO authority."""
    if placement.rule_id != constraint.rule_id:
        raise ValueError("HARNESS_IF_PLACEMENT_RULE_MISMATCH")
    if not constraint.admits(placement.surface):
        raise ValueError("HARNESS_IF_INADMISSIBLE_SURFACE")
    assessment = checker(constraint, placement, evidence)
    return RuleVerdict(
        agent_id=agent_id,
        item_id=item_id,
        round_id=round_id,
        rule_id=constraint.rule_id,
        surface=placement.surface,
        status=assessment.status,
        method=constraint.scoring_method,
        reason=assessment.reason,
        evidence_refs=assessment.evidence_refs,
        cascade_id=cascade_id,
        missing_artifact_ref=missing_artifact_ref,
    )


class PriorProbe(FrozenModel):
    rule_id: str
    build_id: str
    target_rule_withheld: bool
    observed_prior: Prior
    evidence_ref: str = ""


class PriorEvidence(FrozenModel):
    rule_id: str
    prior: Prior | None
    lineage: PriorLineage
    probes: int
    consensus_count: int
    reason: str


def derive_zero_injection_prior(
    rule_id: str,
    probes: Sequence[PriorProbe],
    *,
    required_builds: int = 9,
    consensus: int = 5,
) -> PriorEvidence:
    """Derive a prior only when >=5 of 9 withheld-rule probes agree."""
    relevant = [probe for probe in probes if probe.rule_id == rule_id]
    if any(not probe.target_rule_withheld for probe in relevant):
        raise ValueError("HARNESS_IF_PRIOR_PROBE_LEAKED_TARGET_RULE")
    builds = {probe.build_id for probe in relevant}
    if len(builds) != len(relevant):
        raise ValueError("HARNESS_IF_DUPLICATE_PRIOR_PROBE_BUILD")
    if len(relevant) < required_builds:
        return PriorEvidence(
            rule_id=rule_id,
            prior=None,
            lineage=PriorLineage.ZERO_INJECTION,
            probes=len(relevant),
            consensus_count=0,
            reason="INSUFFICIENT_ZERO_INJECTION_PROBES",
        )
    label, count = Counter(probe.observed_prior for probe in relevant).most_common(1)[0]
    if count < consensus:
        return PriorEvidence(
            rule_id=rule_id,
            prior=None,
            lineage=PriorLineage.ZERO_INJECTION,
            probes=len(relevant),
            consensus_count=count,
            reason="NO_ZERO_INJECTION_CONSENSUS",
        )
    return PriorEvidence(
        rule_id=rule_id,
        prior=label,
        lineage=PriorLineage.ZERO_INJECTION,
        probes=len(relevant),
        consensus_count=count,
        reason="ZERO_INJECTION_CONSENSUS",
    )


def failure_class(modality: Modality) -> FailureClass:
    if modality in (
        Modality.REQUIRE,
        Modality.CONDITIONAL_REQUIRE,
        Modality.LIMIT_MIN,
    ):
        return FailureClass.SHORTFALL
    if modality in (Modality.FORBID, Modality.LIMIT_MAX):
        return FailureClass.OVERSTEP
    return FailureClass.PREFERENCE


def deduplicate_cascades(
    verdicts: Sequence[RuleVerdict],
    library: Mapping[str, Constraint],
) -> tuple[RuleVerdict, ...]:
    """Retain one highest-severity fail per cascade; dependents become no-opportunity."""
    groups: dict[tuple[str, str, int, str], list[int]] = defaultdict(list)
    result = list(verdicts)
    for index, verdict in enumerate(verdicts):
        if verdict.status == VerdictStatus.FAIL and verdict.cascade_id:
            key = (
                verdict.agent_id,
                verdict.item_id,
                verdict.round_id,
                verdict.cascade_id,
            )
            groups[key].append(index)
    for indices in groups.values():
        if len(indices) < 2:
            continue
        keeper = max(
            indices,
            key=lambda i: (
                library[verdicts[i].rule_id].severity.weight,
                verdicts[i].rule_id,
            ),
        )
        for index in indices:
            if index == keeper:
                continue
            old = result[index]
            result[index] = old.model_copy(
                update={
                    "status": VerdictStatus.NO_OPPORTUNITY,
                    "reason": f"CASCADE_DEDUP:{old.reason}",
                }
            )
    return tuple(result)


def cascade_fairness_exclusions(
    verdicts: Sequence[RuleVerdict],
    *,
    min_agents: int = 5,
    threshold: float = 0.5,
) -> frozenset[str]:
    """Exclude design gaps when >=50% of at least five agents miss the artifact."""
    by_rule: dict[str, dict[str, RuleVerdict]] = defaultdict(dict)
    for verdict in verdicts:
        by_rule[verdict.rule_id][verdict.agent_id] = verdict
    excluded: set[str] = set()
    for rule_id, by_agent in by_rule.items():
        if len(by_agent) < min_agents:
            continue
        missing = sum(
            verdict.status == VerdictStatus.NO_OPPORTUNITY
            and verdict.missing_artifact_ref is not None
            for verdict in by_agent.values()
        )
        if missing / len(by_agent) >= threshold:
            excluded.add(rule_id)
    return frozenset(excluded)


class AgentMetrics(FrozenModel):
    agent_id: str
    accuracy: float | None
    filtered_accuracy: float | None
    discrimination_weighted_accuracy: float | None
    against_prior_accuracy: float | None
    eligible: int
    filtered_eligible: int
    against_prior_eligible: int


class CohortMetrics(FrozenModel):
    agents: tuple[AgentMetrics, ...]
    discrimination_weights: Mapping[str, float]
    discriminating_observations: frozenset[tuple[str, int, str]]
    excluded_design_gap_rules: frozenset[str] = frozenset()


def _rate(values: Sequence[int]) -> float | None:
    return sum(values) / len(values) if values else None


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    denominator = math.sqrt(
        sum(value * value for value in dx) * sum(value * value for value in dy)
    )
    if denominator == 0:
        return None
    return sum(x * y for x, y in zip(dx, dy, strict=True)) / denominator


def _eligible_by_agent(
    verdicts: Iterable[RuleVerdict],
    excluded: frozenset[str],
) -> dict[str, list[RuleVerdict]]:
    by_agent: dict[str, list[RuleVerdict]] = defaultdict(list)
    for verdict in verdicts:
        if verdict.eligible and verdict.rule_id not in excluded:
            by_agent[verdict.agent_id].append(verdict)
    return by_agent


def _discriminating_keys(
    verdicts: Sequence[RuleVerdict],
    excluded: frozenset[str],
) -> frozenset[tuple[str, int, str]]:
    outcomes: dict[tuple[str, int, str], set[int]] = defaultdict(set)
    for verdict in verdicts:
        if verdict.eligible and verdict.rule_id not in excluded:
            outcomes[verdict.observation_key].add(verdict.z)
    return frozenset(key for key, values in outcomes.items() if len(values) > 1)


def _discrimination_weights(
    by_agent: Mapping[str, Sequence[RuleVerdict]],
) -> dict[str, float]:
    overall = {
        agent: _rate([verdict.z for verdict in rows])
        for agent, rows in by_agent.items()
    }
    per_rule_agent: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for agent, rows in by_agent.items():
        for verdict in rows:
            per_rule_agent[verdict.rule_id][agent].append(verdict.z)
    weights: dict[str, float] = {}
    for rule_id, per_agent in per_rule_agent.items():
        xs: list[float] = []
        ys: list[float] = []
        for agent, values in per_agent.items():
            if overall[agent] is None:
                continue
            xs.append(sum(values) / len(values))
            ys.append(float(overall[agent]))
        correlation = _pearson(xs, ys)
        weights[rule_id] = (
            max(0.0, correlation)
            if correlation is not None and math.isfinite(correlation)
            else 0.0
        )
    return weights


def compute_metrics(
    verdicts: Sequence[RuleVerdict],
    library: Mapping[str, Constraint],
    *,
    design_gap_rules: frozenset[str] = frozenset(),
) -> CohortMetrics:
    """Compute paper equations Acc, F-Acc, DW-Acc and AP-Acc over eligible rows."""
    unknown = sorted({verdict.rule_id for verdict in verdicts} - set(library))
    if unknown:
        raise ValueError(f"HARNESS_IF_UNKNOWN_VERDICT_RULES:{','.join(unknown)}")
    by_agent = _eligible_by_agent(verdicts, design_gap_rules)
    discriminating = _discriminating_keys(verdicts, design_gap_rules)
    weights = _discrimination_weights(by_agent)
    rows: list[AgentMetrics] = []
    for agent in sorted(by_agent):
        eligible = by_agent[agent]
        binary = [verdict.z for verdict in eligible]
        filtered = [
            verdict.z
            for verdict in eligible
            if verdict.observation_key in discriminating
        ]
        against_prior = [
            verdict.z
            for verdict in eligible
            if library[verdict.rule_id].prior == Prior.AGAINST
        ]
        weighted_numerator = sum(
            weights.get(verdict.rule_id, 0.0) * verdict.z
            for verdict in eligible
        )
        weighted_denominator = sum(
            weights.get(verdict.rule_id, 0.0) for verdict in eligible
        )
        rows.append(
            AgentMetrics(
                agent_id=agent,
                accuracy=_rate(binary),
                filtered_accuracy=_rate(filtered),
                discrimination_weighted_accuracy=(
                    weighted_numerator / weighted_denominator
                    if weighted_denominator > 0
                    else None
                ),
                against_prior_accuracy=_rate(against_prior),
                eligible=len(binary),
                filtered_eligible=len(filtered),
                against_prior_eligible=len(against_prior),
            )
        )
    return CohortMetrics(
        agents=tuple(rows),
        discrimination_weights=weights,
        discriminating_observations=discriminating,
        excluded_design_gap_rules=design_gap_rules,
    )


def common_support(
    verdicts: Sequence[RuleVerdict],
    *,
    agents: Sequence[str] | None = None,
) -> tuple[RuleVerdict, ...]:
    """Keep item/round/rule keys with clean pass/fail for every cohort agent."""
    cohort = frozenset(agents or sorted({verdict.agent_id for verdict in verdicts}))
    by_key: dict[tuple[str, int, str], dict[str, RuleVerdict]] = defaultdict(dict)
    for verdict in verdicts:
        if verdict.agent_id in cohort and verdict.eligible:
            by_key[verdict.observation_key][verdict.agent_id] = verdict
    keys = {
        key
        for key, by_agent in by_key.items()
        if frozenset(by_agent) == cohort
    }
    return tuple(
        verdict
        for verdict in verdicts
        if verdict.agent_id in cohort
        and verdict.observation_key in keys
        and verdict.eligible
    )


def grouped_accuracy(
    verdicts: Sequence[RuleVerdict],
    library: Mapping[str, Constraint],
    *,
    by: str,
) -> dict[str, float]:
    groups: dict[str, list[int]] = defaultdict(list)
    for verdict in verdicts:
        if not verdict.eligible:
            continue
        if by == "surface":
            key = verdict.surface.value
        elif by == "family":
            key = library[verdict.rule_id].family.value
        else:
            raise ValueError("HARNESS_IF_GROUP_BY_MUST_BE_SURFACE_OR_FAMILY")
        groups[key].append(verdict.z)
    return {
        key: sum(values) / len(values)
        for key, values in sorted(groups.items())
    }


class FailureStats(FrozenModel):
    failure_class: FailureClass
    failures: int
    eligible: int
    failure_rate: float | None


def decompose_failures(
    verdicts: Sequence[RuleVerdict],
    library: Mapping[str, Constraint],
) -> tuple[FailureStats, ...]:
    eligible: Counter[FailureClass] = Counter()
    failures: Counter[FailureClass] = Counter()
    for verdict in verdicts:
        if not verdict.eligible:
            continue
        klass = failure_class(library[verdict.rule_id].modality)
        eligible[klass] += 1
        if verdict.status == VerdictStatus.FAIL:
            failures[klass] += 1
    return tuple(
        FailureStats(
            failure_class=klass,
            failures=failures[klass],
            eligible=eligible[klass],
            failure_rate=(
                failures[klass] / eligible[klass]
                if eligible[klass]
                else None
            ),
        )
        for klass in FailureClass
    )


class ConflictRun(FrozenModel):
    model_id: str
    pair_id: str
    direction: str
    surface_a: Surface
    surface_b: Surface
    winner: Surface | None

    @model_validator(mode="after")
    def validate_conflict(self) -> "ConflictRun":
        if self.surface_a == self.surface_b:
            raise ValueError("HARNESS_IF_CONFLICT_REQUIRES_TWO_SURFACES")
        if (
            self.surface_a not in CONFIGURABLE_SURFACES
            or self.surface_b not in CONFIGURABLE_SURFACES
        ):
            raise ValueError("HARNESS_IF_E0_ONLY_CONFIGURABLE_SURFACES")
        if self.winner is not None and self.winner not in (
            self.surface_a,
            self.surface_b,
        ):
            raise ValueError("HARNESS_IF_CONFLICT_WINNER_NOT_IN_PAIR")
        return self


class BradleyTerryResult(FrozenModel):
    log_strengths: Mapping[Surface, float]
    decisive_runs: int
    converged: bool
    iterations: int


def bradley_terry(
    runs: Sequence[ConflictRun],
    *,
    max_iter: int = 10_000,
    tolerance: float = 1e-12,
) -> BradleyTerryResult:
    """Fit pooled Bradley-Terry strengths by MM; errors/ties are excluded."""
    surfaces = sorted(CONFIGURABLE_SURFACES, key=lambda surface: surface.value)
    index = {surface: i for i, surface in enumerate(surfaces)}
    wins = [0.0] * len(surfaces)
    matches = [[0.0] * len(surfaces) for _ in surfaces]
    decisive = 0
    for run in runs:
        if run.winner is None:
            continue
        left = index[run.surface_a]
        right = index[run.surface_b]
        matches[left][right] += 1
        matches[right][left] += 1
        wins[index[run.winner]] += 1
        decisive += 1
    if decisive == 0:
        raise ValueError("HARNESS_IF_E0_REQUIRES_DECISIVE_RUNS")
    strengths = [1.0] * len(surfaces)
    converged = False
    iteration = 0
    for iteration in range(1, max_iter + 1):
        updated: list[float] = []
        for i in range(len(surfaces)):
            denominator = 0.0
            for j in range(len(surfaces)):
                if i != j and matches[i][j]:
                    denominator += matches[i][j] / (strengths[i] + strengths[j])
            updated.append(
                max(wins[i] / denominator, 1e-15)
                if denominator
                else strengths[i]
            )
        log_mean = sum(math.log(value) for value in updated) / len(updated)
        scale = math.exp(log_mean)
        updated = [value / scale for value in updated]
        delta = max(
            abs(math.log(updated[i]) - math.log(strengths[i]))
            for i in range(len(strengths))
        )
        strengths = updated
        if delta < tolerance:
            converged = True
            break
    return BradleyTerryResult(
        log_strengths={
            surface: math.log(strengths[index[surface]])
            for surface in surfaces
        },
        decisive_runs=decisive,
        converged=converged,
        iterations=iteration,
    )


def precedence_support(
    runs: Sequence[ConflictRun],
    *,
    replicates: int = 10_000,
    seed: int = 260811727,
    top: frozenset[Surface] = frozenset(
        {
            Surface.SYSTEM_PROMPT,
            Surface.PROJECT_FILE,
            Surface.USER_INSTRUCTION,
        }
    ),
    middle: Surface = Surface.TOOL_DESCRIPTION,
    bottom: Surface = Surface.SKILL_DESCRIPTION,
) -> float:
    """Crossed-bootstrap support for top-group > middle > bottom precedence."""
    if replicates < 1:
        raise ValueError("HARNESS_IF_BOOTSTRAP_REPLICATES_MUST_BE_POSITIVE")
    models = sorted({run.model_id for run in runs})
    pairs = sorted({run.pair_id for run in runs})
    if not models or not pairs:
        raise ValueError("HARNESS_IF_BOOTSTRAP_REQUIRES_MODELS_AND_PAIRS")
    rng = random.Random(seed)
    support = 0
    for _ in range(replicates):
        model_counts = Counter(rng.choices(models, k=len(models)))
        pair_counts = Counter(rng.choices(pairs, k=len(pairs)))
        sample: list[ConflictRun] = []
        for run in runs:
            copies = model_counts[run.model_id] * pair_counts[run.pair_id]
            if copies:
                sample.extend([run] * copies)
        if not any(run.winner is not None for run in sample):
            continue
        strengths = bradley_terry(sample).log_strengths
        if (
            min(strengths[surface] for surface in top)
            > strengths[middle]
            > strengths[bottom]
        ):
            support += 1
    return support / replicates


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_jsonable(item) for item in value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def fingerprint(value: Any) -> str:
    """Deterministic snapshot identity; this is not a BRCE actuation Receipt."""
    payload = json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


class EvaluationSnapshot(FrozenModel):
    library: tuple[Constraint, ...]
    verdicts: tuple[RuleVerdict, ...]
    design_gap_rules: frozenset[str] = frozenset()

    def score(self) -> CohortMetrics:
        return compute_metrics(
            self.verdicts,
            {rule.rule_id: rule for rule in self.library},
            design_gap_rules=self.design_gap_rules,
        )

    @property
    def snapshot_fingerprint(self) -> str:
        return fingerprint(self)


class EvaluationReplay(FrozenModel):
    snapshot_fingerprint: str
    metrics_fingerprint: str
    metrics: CohortMetrics


def replay(snapshot: EvaluationSnapshot) -> EvaluationReplay:
    """Recompute scores from the exact admitted snapshot for deterministic replay."""
    metrics = snapshot.score()
    return EvaluationReplay(
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        metrics_fingerprint=fingerprint(metrics),
        metrics=metrics,
    )
