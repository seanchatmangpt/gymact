from __future__ import annotations

import pytest
from pydantic import ValidationError

from gymact import dcm
from gymact.survival_experiment import (
    InformationTopology,
    Machinery,
    SurvivalEpisode,
    SurvivalExperiment,
    SurvivalPolicy,
    SurvivalScenario,
    SurvivalStep,
    ToolPolicy,
)


def scenario(name: str = "s1") -> SurvivalScenario:
    return SurvivalScenario(
        scenario_id=name,
        subject="git:seanchatmangpt/gymact@0123456789abcdef",
        workload_id="sha256:survival-workload",
        horizon=4,
        terminal_predicate_ref="urn:predicate:goal-ready",
    )


def policy(name: str, machinery: Machinery) -> SurvivalPolicy:
    return SurvivalPolicy(
        policy_id=name,
        machinery=machinery,
        information_topology=InformationTopology.RECEIPT_ONLY,
        tool_policy=ToolPolicy.OPTIONAL,
    )


def test_survival_experiment_materializes_full_cross_product() -> None:
    experiment = SurvivalExperiment(
        experiment_id="survival:v26.9.25",
        scenarios=(scenario("s1"), scenario("s2")),
        policies=(
            policy("llm", Machinery.LLM_NATIVE),
            policy("formal", Machinery.FORMAL_GENERATED),
        ),
    )

    cells = experiment.matrix()

    assert [cell.cell_id for cell in cells] == [
        "s1::llm",
        "s1::formal",
        "s2::llm",
        "s2::formal",
    ]


def test_episode_projects_exact_autofde_survival_schema_without_do_authority() -> None:
    cell = dcm.SurvivalCell(
        scenario=scenario(),
        policy=policy("formal", Machinery.FORMAL_GENERATED),
    )
    episode = dcm.SurvivalEpisode(
        episode_id="episode-1",
        cell=cell,
        steps=(
            SurvivalStep(step=1, phase="OBSERVE"),
            SurvivalStep(
                step=4,
                phase="DO",
                authorized=True,
                admitted=True,
                receipt_id="receipt:4",
                terminal_ready=True,
            ),
        ),
    )

    document = episode.to_autofde_document()

    assert document["schema"] == "autofde-lab.premature-actuation-episode/1"
    assert document["policy_id"] == "formal"
    assert document["horizon"] == 4
    assert document["events"][1]["receipt_id"] == "receipt:4"
    assert document["gymact"]["machinery"] == "formal-generated"
    assert document["gymact"]["information_topology"] == "receipt-only"
    assert document["gymact"]["grants_do_authority"] is False


def test_episode_refuses_step_outside_horizon() -> None:
    cell = dcm.SurvivalCell(
        scenario=scenario(),
        policy=policy("formal", Machinery.FORMAL_GENERATED),
    )

    with pytest.raises(ValidationError, match="SURVIVAL_STEP_EXCEEDS_HORIZON"):
        SurvivalEpisode(
            episode_id="bad",
            cell=cell,
            steps=(SurvivalStep(step=5, phase="OBSERVE"),),
        )


def test_policy_cannot_grant_do_authority() -> None:
    with pytest.raises(ValidationError):
        SurvivalPolicy(
            policy_id="unsafe",
            machinery=Machinery.LLM_TOOLS,
            grants_do_authority=True,
        )


def test_public_dcm_facade_exports_survival_contract() -> None:
    assert dcm.SurvivalExperiment is SurvivalExperiment
    assert dcm.SurvivalPolicy is SurvivalPolicy
    assert dcm.SurvivalScenario is SurvivalScenario
