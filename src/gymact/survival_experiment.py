"""Scenario x policy cross-product for premature-actuation survival experiments.

GymAct owns the bounded experiment design. autofde-lab owns survival analysis and
standing. This module manufactures exact scenario/policy cells and exports observed
step records in the autofde-lab premature-actuation episode schema.

No method here grants DO authority or performs external actuation.
"""

from __future__ import annotations

from enum import StrEnum
from itertools import product
from math import prod
from typing import Literal

from pydantic import Field, model_validator

from gymact.evidence import digest
from gymact.models import FrozenModel


class InformationTopology(StrEnum):
    ISOLATED = "isolated"
    STAR = "star"
    TREE = "tree"
    MESH = "mesh"
    BLACKBOARD = "blackboard"
    BROADCAST = "broadcast"
    AUTHORITY_FILTERED = "authority-filtered"
    RECEIPT_ONLY = "receipt-only"


class ToolPolicy(StrEnum):
    NONE = "none"
    OPTIONAL = "optional"
    MANDATORY = "mandatory"


class Machinery(StrEnum):
    LLM_NATIVE = "llm-native"
    LLM_TOOLS = "llm-tools"
    SELECTIVE_LLM = "selective-llm"
    PLANNER_LLM_RESIDUE = "planner-llm-residue"
    FORMAL_GENERATED = "formal-generated"


class SurvivalScenario(FrozenModel):
    """One fixed world/horizon subject for a policy comparison."""

    scenario_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    workload_id: str = Field(min_length=1)
    horizon: int = Field(ge=1)
    terminal_predicate_ref: str = Field(min_length=1)


class SurvivalPolicy(FrozenModel):
    """Policy factors varied while the scenario remains exact."""

    policy_id: str = Field(min_length=1)
    machinery: Machinery
    information_topology: InformationTopology = InformationTopology.ISOLATED
    tool_policy: ToolPolicy = ToolPolicy.OPTIONAL
    authority_ceiling: Literal["OBSERVE|SELECT|CONSTRUCT"] = "OBSERVE|SELECT|CONSTRUCT"
    grants_do_authority: Literal[False] = False


class SurvivalFactor(FrozenModel):
    """One reversible perturbation dimension layered over scenario x policy."""

    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_\\-]*$")
    levels: tuple[str, ...]

    @model_validator(mode="after")
    def require_distinct_levels(self) -> SurvivalFactor:
        if not self.levels:
            raise ValueError("SURVIVAL_FACTOR_LEVEL_REQUIRED")
        if any(not level.strip() or level != level.strip() for level in self.levels):
            raise ValueError("SURVIVAL_FACTOR_LEVEL_INVALID")
        if len(self.levels) != len(set(self.levels)):
            raise ValueError("SURVIVAL_FACTOR_LEVEL_DUPLICATE")
        return self


class SurvivalFactorAssignment(FrozenModel):
    name: str = Field(min_length=1)
    level: str = Field(min_length=1)


class SurvivalCell(FrozenModel):
    """One exact scenario x policy experiment cell."""

    scenario: SurvivalScenario
    policy: SurvivalPolicy

    @property
    def cell_id(self) -> str:
        return f"{self.scenario.scenario_id}::{self.policy.policy_id}"


class SurvivalRunCase(FrozenModel):
    """One deterministic factorial case. It is a construction, not an execution grant."""

    cell: SurvivalCell
    assignments: tuple[SurvivalFactorAssignment, ...] = ()
    repetition: int = Field(ge=0)
    seed: int = Field(ge=0)
    authority: Literal["none"] = "none"
    grants_do_authority: Literal[False] = False

    @property
    def factor_digest(self) -> str:
        return digest([assignment.model_dump(mode="json") for assignment in self.assignments])

    @property
    def analysis_policy_id(self) -> str:
        if not self.assignments:
            return self.cell.policy.policy_id
        return f"{self.cell.policy.policy_id}::{self.factor_digest[:16]}"

    @property
    def case_id(self) -> str:
        identity = {
            "cell_id": self.cell.cell_id,
            "assignments": [assignment.model_dump(mode="json") for assignment in self.assignments],
            "repetition": self.repetition,
            "seed": self.seed,
        }
        return f"{self.cell.cell_id}::{digest(identity)[:16]}"


class SurvivalStep(FrozenModel):
    """One observed decision step; a record, never ambient actuation authority."""

    step: int = Field(ge=1)
    phase: Literal["OBSERVE", "SELECT", "CONSTRUCT", "VERIFY", "DO"]
    exact_subject: bool = True
    authorized: bool = True
    admitted: bool = True
    receipt_id: str | None = None
    terminal_ready: bool = True
    tool_invoked: bool = False
    llm_tokens: int = Field(ge=0, default=0)
    replay_verified: bool = False
    guards_installed: tuple[str, ...] = ()


class SurvivalEpisode(FrozenModel):
    """Observed steps for one exact scenario/policy cell."""

    episode_id: str = Field(min_length=1)
    cell: SurvivalCell
    steps: tuple[SurvivalStep, ...]
    run_case: SurvivalRunCase | None = None

    @model_validator(mode="after")
    def bind_steps_to_horizon(self) -> SurvivalEpisode:
        values = [step.step for step in self.steps]
        if len(values) != len(set(values)):
            raise ValueError("SURVIVAL_STEP_DUPLICATE")
        if values and max(values) > self.cell.scenario.horizon:
            raise ValueError("SURVIVAL_STEP_EXCEEDS_HORIZON")
        if self.run_case is not None and self.run_case.cell != self.cell:
            raise ValueError("SURVIVAL_RUN_CASE_CELL_MISMATCH")
        return self

    def to_autofde_document(self) -> dict:
        scenario = self.cell.scenario
        policy = self.cell.policy
        return {
            "schema": "autofde-lab.premature-actuation-episode/1",
            "subject": scenario.subject,
            "workload_id": scenario.workload_id,
            "policy_id": (
                self.run_case.analysis_policy_id if self.run_case is not None else policy.policy_id
            ),
            "episode_id": self.episode_id,
            "horizon": scenario.horizon,
            "events": [
                step.model_dump(mode="json")
                for step in sorted(self.steps, key=lambda item: item.step)
            ],
            "gymact": {
                "scenario_id": scenario.scenario_id,
                "terminal_predicate_ref": scenario.terminal_predicate_ref,
                "machinery": policy.machinery.value,
                "information_topology": policy.information_topology.value,
                "tool_policy": policy.tool_policy.value,
                "authority_ceiling": policy.authority_ceiling,
                "grants_do_authority": policy.grants_do_authority,
                "run_case_id": self.run_case.case_id if self.run_case else None,
                "repetition": self.run_case.repetition if self.run_case else None,
                "seed": self.run_case.seed if self.run_case else None,
                "factor_assignments": (
                    [assignment.model_dump(mode="json") for assignment in self.run_case.assignments]
                    if self.run_case
                    else []
                ),
            },
        }


class SurvivalExperiment(FrozenModel):
    """Manufacture a deterministic scenario x policy matrix."""

    experiment_id: str = Field(min_length=1)
    scenarios: tuple[SurvivalScenario, ...]
    policies: tuple[SurvivalPolicy, ...]
    factors: tuple[SurvivalFactor, ...] = ()
    repetitions: int = Field(ge=1, default=1)
    seed_base: int = Field(ge=0, default=0)
    max_cases: int = Field(ge=1, le=1_000_000, default=100_000)

    @model_validator(mode="after")
    def require_closed_unique_factors(self) -> SurvivalExperiment:
        scenario_ids = [scenario.scenario_id for scenario in self.scenarios]
        policy_ids = [policy.policy_id for policy in self.policies]
        if not scenario_ids or not policy_ids:
            raise ValueError("SURVIVAL_FACTORS_EMPTY")
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("SURVIVAL_SCENARIO_ID_DUPLICATE")
        if len(policy_ids) != len(set(policy_ids)):
            raise ValueError("SURVIVAL_POLICY_ID_DUPLICATE")
        factor_names = [factor.name for factor in self.factors]
        if len(factor_names) != len(set(factor_names)):
            raise ValueError("SURVIVAL_FACTOR_NAME_DUPLICATE")
        if self.case_count > self.max_cases:
            raise ValueError(f"SURVIVAL_MAX_CASES_EXCEEDED:{self.case_count}>{self.max_cases}")
        return self

    @property
    def case_count(self) -> int:
        factor_width = prod(len(factor.levels) for factor in self.factors)
        return len(self.scenarios) * len(self.policies) * factor_width * self.repetitions

    def matrix(self) -> tuple[SurvivalCell, ...]:
        return tuple(
            SurvivalCell(scenario=scenario, policy=policy)
            for scenario in self.scenarios
            for policy in self.policies
        )

    def cases(self) -> tuple[SurvivalRunCase, ...]:
        """Expand scenario x policy x perturbations x repetitions deterministically."""

        level_matrix = (
            tuple(product(*(factor.levels for factor in self.factors))) if self.factors else ((),)
        )
        cases: list[SurvivalRunCase] = []
        ordinal = 0
        for cell in self.matrix():
            for levels in level_matrix:
                assignments = tuple(
                    SurvivalFactorAssignment(name=factor.name, level=level)
                    for factor, level in zip(self.factors, levels, strict=True)
                )
                for repetition in range(self.repetitions):
                    cases.append(
                        SurvivalRunCase(
                            cell=cell,
                            assignments=assignments,
                            repetition=repetition,
                            seed=self.seed_base + ordinal,
                        )
                    )
                    ordinal += 1
        if len(cases) != self.case_count:
            raise AssertionError("SURVIVAL_FACTORIAL_CLOSURE_BROKEN")
        return tuple(cases)
