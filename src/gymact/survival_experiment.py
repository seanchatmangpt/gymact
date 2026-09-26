"""Scenario × policy cross-product for premature-actuation survival experiments.

GymAct owns the bounded experiment design. autofde-lab owns survival analysis and
standing. This module manufactures exact scenario/policy cells and exports observed
step records in the autofde-lab premature-actuation episode schema.

No method here grants DO authority or performs external actuation.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

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
    authority_ceiling: Literal["OBSERVE|SELECT|CONSTRUCT"] = (
        "OBSERVE|SELECT|CONSTRUCT"
    )
    grants_do_authority: Literal[False] = False


class SurvivalCell(FrozenModel):
    """One exact scenario × policy experiment cell."""

    scenario: SurvivalScenario
    policy: SurvivalPolicy

    @property
    def cell_id(self) -> str:
        return f"{self.scenario.scenario_id}::{self.policy.policy_id}"


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


class SurvivalEpisode(FrozenModel):
    """Observed steps for one exact scenario/policy cell."""

    episode_id: str = Field(min_length=1)
    cell: SurvivalCell
    steps: tuple[SurvivalStep, ...]

    @model_validator(mode="after")
    def bind_steps_to_horizon(self) -> "SurvivalEpisode":
        values = [step.step for step in self.steps]
        if len(values) != len(set(values)):
            raise ValueError("SURVIVAL_STEP_DUPLICATE")
        if values and max(values) > self.cell.scenario.horizon:
            raise ValueError("SURVIVAL_STEP_EXCEEDS_HORIZON")
        return self

    def to_autofde_document(self) -> dict:
        scenario = self.cell.scenario
        policy = self.cell.policy
        return {
            "schema": "autofde-lab.premature-actuation-episode/1",
            "subject": scenario.subject,
            "workload_id": scenario.workload_id,
            "policy_id": policy.policy_id,
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
            },
        }


class SurvivalExperiment(FrozenModel):
    """Manufacture a deterministic scenario × policy matrix."""

    experiment_id: str = Field(min_length=1)
    scenarios: tuple[SurvivalScenario, ...]
    policies: tuple[SurvivalPolicy, ...]

    @model_validator(mode="after")
    def require_closed_unique_factors(self) -> "SurvivalExperiment":
        scenario_ids = [scenario.scenario_id for scenario in self.scenarios]
        policy_ids = [policy.policy_id for policy in self.policies]
        if not scenario_ids or not policy_ids:
            raise ValueError("SURVIVAL_FACTORS_EMPTY")
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("SURVIVAL_SCENARIO_ID_DUPLICATE")
        if len(policy_ids) != len(set(policy_ids)):
            raise ValueError("SURVIVAL_POLICY_ID_DUPLICATE")
        return self

    def matrix(self) -> tuple[SurvivalCell, ...]:
        return tuple(
            SurvivalCell(scenario=scenario, policy=policy)
            for scenario in self.scenarios
            for policy in self.policies
        )
