from __future__ import annotations

import pytest
from pydantic import ValidationError

from gymact import dcm
from gymact.survival_experiment import (
    Machinery,
    SurvivalEpisode,
    SurvivalExperiment,
    SurvivalFactor,
    SurvivalPolicy,
    SurvivalScenario,
    SurvivalStep,
)


def scenario() -> SurvivalScenario:
    return SurvivalScenario(
        scenario_id="world-1",
        subject="git:seanchatmangpt/gymact@0123456789abcdef",
        workload_id="sha256:survival-factorial-workload",
        horizon=8,
        terminal_predicate_ref="urn:predicate:goal-ready",
    )


def policy(policy_id: str, machinery: Machinery) -> SurvivalPolicy:
    return SurvivalPolicy(policy_id=policy_id, machinery=machinery)


def test_factorial_cases_close_full_bounded_cross_product() -> None:
    experiment = SurvivalExperiment(
        experiment_id="survival-factorial:v26.9.25",
        scenarios=(scenario(),),
        policies=(
            policy("llm", Machinery.LLM_NATIVE),
            policy("formal", Machinery.FORMAL_GENERATED),
        ),
        factors=(
            SurvivalFactor(name="authority", levels=("full", "filtered")),
            SurvivalFactor(name="transport", levels=("stable", "lossy")),
        ),
        repetitions=2,
        seed_base=100,
    )

    cases = experiment.cases()

    assert experiment.case_count == 16
    assert len(cases) == 16
    assert len({case.case_id for case in cases}) == 16
    assert [case.seed for case in cases] == list(range(100, 116))
    assert all(case.authority == "none" for case in cases)
    assert all(case.grants_do_authority is False for case in cases)
    assert {
        tuple((assignment.name, assignment.level) for assignment in case.assignments)
        for case in cases
    } == {
        (("authority", "full"), ("transport", "stable")),
        (("authority", "full"), ("transport", "lossy")),
        (("authority", "filtered"), ("transport", "stable")),
        (("authority", "filtered"), ("transport", "lossy")),
    }


def test_repetitions_share_analysis_policy_identity_for_same_factor_assignment() -> None:
    experiment = SurvivalExperiment(
        experiment_id="repeat",
        scenarios=(scenario(),),
        policies=(policy("formal", Machinery.FORMAL_GENERATED),),
        factors=(SurvivalFactor(name="transport", levels=("stable",)),),
        repetitions=3,
    )

    cases = experiment.cases()

    assert len({case.analysis_policy_id for case in cases}) == 1
    assert len({case.case_id for case in cases}) == 3


def test_episode_projects_recurrence_replay_and_factor_evidence() -> None:
    experiment = SurvivalExperiment(
        experiment_id="projection",
        scenarios=(scenario(),),
        policies=(policy("formal", Machinery.FORMAL_GENERATED),),
        factors=(SurvivalFactor(name="authority", levels=("filtered",)),),
    )
    run_case = experiment.cases()[0]
    episode = SurvivalEpisode(
        episode_id=run_case.case_id,
        cell=run_case.cell,
        run_case=run_case,
        steps=(
            SurvivalStep(
                step=2,
                phase="DO",
                authorized=False,
                receipt_id="receipt:2",
                replay_verified=True,
                llm_tokens=0,
            ),
            SurvivalStep(
                step=3,
                phase="VERIFY",
                guards_installed=("UNAUTHORIZED_DO",),
            ),
        ),
    )

    document = episode.to_autofde_document()

    assert document["policy_id"] == run_case.analysis_policy_id
    assert document["events"][0]["replay_verified"] is True
    assert document["events"][1]["guards_installed"] == ["UNAUTHORIZED_DO"]
    assert document["gymact"]["run_case_id"] == run_case.case_id
    assert document["gymact"]["factor_assignments"] == [
        {"name": "authority", "level": "filtered"}
    ]
    assert document["gymact"]["grants_do_authority"] is False


def test_factorial_space_refuses_case_explosion_before_construction() -> None:
    with pytest.raises(ValidationError, match="SURVIVAL_MAX_CASES_EXCEEDED"):
        SurvivalExperiment(
            experiment_id="too-wide",
            scenarios=(scenario(),),
            policies=(policy("formal", Machinery.FORMAL_GENERATED),),
            factors=(SurvivalFactor(name="fault", levels=("a", "b", "c")),),
            repetitions=2,
            max_cases=5,
        )


def test_public_dcm_facade_exports_factorial_contracts() -> None:
    assert dcm.SurvivalFactor is SurvivalFactor
    assert dcm.SurvivalRunCase.__name__ == "SurvivalRunCase"
