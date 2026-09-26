from __future__ import annotations

from gymact.survival_experiment import (
    Machinery,
    SurvivalEpisode,
    SurvivalExperiment,
    SurvivalScenario,
    SurvivalStep,
)
from gymact.survival_manifest import build_survival_manifest
from gymact.survival_observation import qualify_observation_closure
from gymact.survival_suite import canonical_fault_suite, canonical_policy_suite


def small_experiment() -> SurvivalExperiment:
    return SurvivalExperiment(
        experiment_id="closure:v26.9.25",
        scenarios=(
            SurvivalScenario(
                scenario_id="world",
                subject="git:gymact/example@0123456789abcdef",
                workload_id="sha256:closure",
                horizon=3,
                terminal_predicate_ref="urn:goal",
            ),
        ),
        policies=(
            canonical_policy_suite()[0],
            canonical_policy_suite()[-1],
        ),
        factors=(canonical_fault_suite()[1],),
        repetitions=1,
        seed_base=20,
    )


def observed_document(case) -> dict:
    return SurvivalEpisode(
        episode_id=case.case_id,
        cell=case.cell,
        run_case=case,
        steps=(
            SurvivalStep(step=1, phase="OBSERVE"),
            SurvivalStep(
                step=3,
                phase="DO",
                receipt_id=f"receipt:{case.case_id}",
            ),
        ),
    ).to_autofde_document()


def test_canonical_suite_spans_five_machinery_classes_and_four_fault_axes() -> None:
    policies = canonical_policy_suite()
    faults = canonical_fault_suite()

    assert [policy.machinery for policy in policies] == [
        Machinery.LLM_NATIVE,
        Machinery.LLM_TOOLS,
        Machinery.SELECTIVE_LLM,
        Machinery.PLANNER_LLM_RESIDUE,
        Machinery.FORMAL_GENERATED,
    ]
    assert [factor.name for factor in faults] == [
        "authority",
        "transport",
        "evidence",
        "terminal_signal",
    ]
    assert all(policy.grants_do_authority is False for policy in policies)


def test_observation_closure_requires_exact_manifest_case_coverage() -> None:
    experiment = small_experiment()
    manifest = build_survival_manifest(experiment)
    docs = [observed_document(case) for case in experiment.cases()]

    closure = qualify_observation_closure(manifest, docs)

    assert closure.complete is True
    assert closure.standing == "STRUCTURAL"
    assert closure.expected_case_count == closure.observed_unique_case_count
    assert closure.missing_case_ids == ()
    assert closure.unknown_case_ids == ()
    assert closure.duplicate_case_ids == ()
    assert closure.identity_drift_episode_ids == ()
    assert closure.authority == "none"
    assert closure.actuation_performed is False


def test_observation_closure_types_every_inventory_failure() -> None:
    experiment = small_experiment()
    manifest = build_survival_manifest(experiment)
    cases = experiment.cases()

    clean = observed_document(cases[0])
    duplicate = observed_document(cases[0])

    unknown = observed_document(cases[1])
    unknown["gymact"]["run_case_id"] = "case:unknown"

    drift = observed_document(cases[2])
    drift["gymact"]["seed"] = 999999

    closure = qualify_observation_closure(
        manifest,
        [clean, duplicate, unknown, drift],
    )

    assert closure.complete is False
    assert closure.standing == "PARTIAL"
    assert cases[0].case_id in closure.duplicate_case_ids
    assert "case:unknown" in closure.unknown_case_ids
    assert drift["episode_id"] in closure.identity_drift_episode_ids
    assert closure.missing_case_ids
