"""Counterbalanced RACaP pairing over the GymAct survival factorial design.

The survival experiment owns scenario x policy x perturbation x repetition.
The RACaP paired-world contract owns champion/candidate evidence. This module
takes their product without granting promotion or production DO authority.
"""

from __future__ import annotations

from typing import Literal, Self

from gymact.evidence import digest
from gymact.models import FrozenModel
from gymact.survival_experiment import SurvivalExperiment, SurvivalRunCase
from pydantic import Field, model_validator

from gymact.racap_paired_world import (
    ObservationExecutor,
    PairedCohortReplay,
    PairedExecutionOrder,
    PairedExecutionRecord,
    PairedWorldCohort,
    PairedWorldIdentity,
    PairedWorldRunner,
)

_CONTENT_DIGEST = r"^(?:sha256|blake3):[0-9a-f]{64}$"


def _digest(value: object) -> str:
    return "blake3:" + digest(value)


class SurvivalPairedCase(FrozenModel):
    """One survival factorial cell lifted into an exact paired-world subject."""

    run_case: SurvivalRunCase
    identity: PairedWorldIdentity
    order: PairedExecutionOrder
    champion_capability_digest: str = Field(pattern=_CONTENT_DIGEST)
    candidate_capability_digest: str = Field(pattern=_CONTENT_DIGEST)
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def bind_distinct_capabilities(self) -> Self:
        if self.champion_capability_digest == self.candidate_capability_digest:
            raise ValueError("SURVIVAL_PAIRED_IDENTICAL_CAPABILITY")
        if self.identity.seed != self.run_case.seed:
            raise ValueError("SURVIVAL_PAIRED_SEED_MISMATCH")
        return self

    @property
    def case_digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


class SurvivalPairedDesign(FrozenModel):
    """Deterministic pairing design over every survival factorial run case."""

    experiment: SurvivalExperiment
    champion_capability_digest: str = Field(pattern=_CONTENT_DIGEST)
    candidate_capability_digest: str = Field(pattern=_CONTENT_DIGEST)
    evaluator_digest: str = Field(pattern=_CONTENT_DIGEST)
    counterbalance_order: bool = True
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def require_distinct_capabilities(self) -> Self:
        if self.champion_capability_digest == self.candidate_capability_digest:
            raise ValueError("SURVIVAL_PAIRED_IDENTICAL_CAPABILITY")
        return self

    @property
    def design_digest(self) -> str:
        return _digest(
            {
                "experiment_id": self.experiment.experiment_id,
                "experiment": self.experiment.model_dump(mode="json"),
                "champion": self.champion_capability_digest,
                "candidate": self.candidate_capability_digest,
                "evaluator": self.evaluator_digest,
                "counterbalance_order": self.counterbalance_order,
            }
        )

    def cases(self) -> tuple[SurvivalPairedCase, ...]:
        cases: list[SurvivalPairedCase] = []
        for ordinal, run_case in enumerate(self.experiment.cases()):
            identity = self.identity_for(run_case)
            order = (
                PairedExecutionOrder.CANDIDATE_FIRST
                if self.counterbalance_order and ordinal % 2
                else PairedExecutionOrder.CHAMPION_FIRST
            )
            cases.append(
                SurvivalPairedCase(
                    run_case=run_case,
                    identity=identity,
                    order=order,
                    champion_capability_digest=self.champion_capability_digest,
                    candidate_capability_digest=self.candidate_capability_digest,
                )
            )
        if len(cases) != self.experiment.case_count:
            raise AssertionError("SURVIVAL_PAIRED_FACTORIAL_CLOSURE_BROKEN")
        return tuple(cases)

    def identity_for(self, run_case: SurvivalRunCase) -> PairedWorldIdentity:
        scenario = run_case.cell.scenario
        world_digest = _digest(
            {
                "scenario": scenario.model_dump(mode="json"),
                "factor_assignments": [
                    assignment.model_dump(mode="json") for assignment in run_case.assignments
                ],
            }
        )
        task_digest = _digest(
            {
                "workload_id": scenario.workload_id,
                "policy_id": run_case.cell.policy.policy_id,
                "run_case_id": run_case.case_id,
            }
        )
        budget_digest = _digest(
            {
                "horizon": scenario.horizon,
                "repetition": run_case.repetition,
            }
        )
        return PairedWorldIdentity(
            world_digest=world_digest,
            task_digest=task_digest,
            seed=run_case.seed,
            budget_digest=budget_digest,
            evaluator_digest=self.evaluator_digest,
        )


class SurvivalPairedResult(FrozenModel):
    """Executed paired factorial evidence, still powerless for promotion."""

    design_digest: str = Field(pattern=_CONTENT_DIGEST)
    records: tuple[PairedExecutionRecord, ...]
    cohort: PairedWorldCohort
    replay: PairedCohortReplay
    result_digest: str = Field(pattern=_CONTENT_DIGEST)
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def bind_replay(self) -> Self:
        if self.replay.cohort_digest != self.cohort.cohort_digest:
            raise ValueError("SURVIVAL_PAIRED_REPLAY_COHORT_MISMATCH")
        if len(self.records) != len(self.cohort.evidence):
            raise ValueError("SURVIVAL_PAIRED_RECORD_COHORT_SIZE_MISMATCH")
        return self


class SurvivalPairedRunner:
    """Execute the full counterbalanced survival x RACaP design."""

    def __init__(self, executor: ObservationExecutor) -> None:
        self.runner = PairedWorldRunner(executor)

    def execute(self, design: SurvivalPairedDesign) -> SurvivalPairedResult:
        paired_cases = design.cases()
        records = tuple(
            self.runner.execute_pair(
                identity=case.identity,
                champion_capability_digest=case.champion_capability_digest,
                candidate_capability_digest=case.candidate_capability_digest,
                order=case.order,
            )
            for case in paired_cases
        )
        cohort = self.runner.court.observe_cohort(tuple(record.run for record in records))
        replay = PairedCohortReplay.from_cohort(cohort)
        result_digest = _digest(
            {
                "design_digest": design.design_digest,
                "case_digests": [case.case_digest for case in paired_cases],
                "execution_digests": [record.execution_digest for record in records],
                "cohort_digest": cohort.cohort_digest,
                "replay_manifest_digest": replay.manifest_digest,
            }
        )
        return SurvivalPairedResult(
            design_digest=design.design_digest,
            records=records,
            cohort=cohort,
            replay=replay,
            result_digest=result_digest,
        )
