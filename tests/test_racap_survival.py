from __future__ import annotations

import pytest
from pydantic import ValidationError

from gymact.racap_paired_world import CapabilityObservation, PairedExecutionOrder
from gymact.racap_survival import (
    SurvivalPairedDesign,
    SurvivalPairedRunner,
)
from gymact.survival_experiment import (
    InformationTopology,
    Machinery,
    SurvivalExperiment,
    SurvivalFactor,
    SurvivalPolicy,
    SurvivalScenario,
    ToolPolicy,
)


def _d(char: str) -> str:
    return "blake3:" + char * 64


def _scenario(name: str) -> SurvivalScenario:
    return SurvivalScenario(
        scenario_id=name,
        subject=f"urn:subject:{name}",
        workload_id=f"urn:workload:{name}",
        horizon=8,
        terminal_predicate_ref="urn:predicate:terminal",
    )


def _policy(name: str, machinery: Machinery) -> SurvivalPolicy:
    return SurvivalPolicy(
        policy_id=name,
        machinery=machinery,
        information_topology=InformationTopology.RECEIPT_ONLY,
        tool_policy=ToolPolicy.OPTIONAL,
    )


def _experiment() -> SurvivalExperiment:
    return SurvivalExperiment(
        experiment_id="survival-racap:v26.9.26",
        scenarios=(_scenario("s1"), _scenario("s2")),
        policies=(
            _policy("formal", Machinery.FORMAL_GENERATED),
            _policy("planner", Machinery.PLANNER_LLM_RESIDUE),
        ),
        factors=(SurvivalFactor(name="latency", levels=("low", "high")),),
        repetitions=2,
        seed_base=40,
    )


def _design(counterbalance: bool = True) -> SurvivalPairedDesign:
    return SurvivalPairedDesign(
        experiment=_experiment(),
        champion_capability_digest=_d("a"),
        candidate_capability_digest=_d("b"),
        evaluator_digest=_d("c"),
        counterbalance_order=counterbalance,
    )


def test_design_lifts_full_survival_factorial_without_losing_cases() -> None:
    design = _design()
    cases = design.cases()

    assert len(cases) == design.experiment.case_count == 16
    assert len({case.identity.identity_digest for case in cases}) == 16
    assert all(case.identity.seed == case.run_case.seed for case in cases)
    assert all(case.authority == "none" for case in cases)


def test_counterbalancing_is_deterministic_and_even() -> None:
    cases = _design().cases()

    assert sum(case.order is PairedExecutionOrder.CHAMPION_FIRST for case in cases) == 8
    assert sum(case.order is PairedExecutionOrder.CANDIDATE_FIRST for case in cases) == 8

    replay = _design().cases()
    assert [case.case_digest for case in cases] == [case.case_digest for case in replay]


def test_non_counterbalanced_design_is_explicit() -> None:
    cases = _design(counterbalance=False).cases()
    assert all(case.order is PairedExecutionOrder.CHAMPION_FIRST for case in cases)


def test_identical_capability_pair_is_refused() -> None:
    with pytest.raises(
        ValidationError,
        match="SURVIVAL_PAIRED_IDENTICAL_CAPABILITY",
    ):
        SurvivalPairedDesign(
            experiment=_experiment(),
            champion_capability_digest=_d("a"),
            candidate_capability_digest=_d("a"),
            evaluator_digest=_d("c"),
        )


class DeterministicExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def __call__(self, identity, capability_digest):
        self.calls.append((capability_digest, identity.seed))
        is_candidate = capability_digest == _d("b")
        return CapabilityObservation(
            capability_digest=capability_digest,
            outcome_digest=_d("d" if is_candidate else "e"),
            consequence_digest=_d("f"),
            receipt_digest=_d("1" if is_candidate else "2"),
            score=0.8 if is_candidate else 0.6,
            success=True,
            steps=6,
        )


def test_runner_executes_all_factorial_pairs_and_manufactures_replay() -> None:
    executor = DeterministicExecutor()
    design = _design()
    result = SurvivalPairedRunner(executor).execute(design)

    assert len(result.records) == 16
    assert len(result.cohort.evidence) == 16
    assert len(executor.calls) == 32
    assert result.design_digest == design.design_digest
    assert result.replay.cohort_digest == result.cohort.cohort_digest
    assert result.result_digest.startswith("blake3:")
    assert result.authority == "none"
    assert all(item.delta == pytest.approx(0.2) for item in result.cohort.evidence)


def test_same_design_replays_to_same_identity_and_result_digest() -> None:
    first = SurvivalPairedRunner(DeterministicExecutor()).execute(_design())
    second = SurvivalPairedRunner(DeterministicExecutor()).execute(_design())

    assert first.design_digest == second.design_digest
    assert first.cohort.cohort_digest == second.cohort.cohort_digest
    assert first.replay.manifest_digest == second.replay.manifest_digest
    assert first.result_digest == second.result_digest
