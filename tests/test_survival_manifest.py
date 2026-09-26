from __future__ import annotations

from gymact.survival_experiment import (
    Machinery,
    SurvivalExperiment,
    SurvivalFactor,
    SurvivalPolicy,
    SurvivalScenario,
)
from gymact.survival_manifest import (
    build_survival_manifest,
    replay_survival_manifest,
)


def experiment(*, transport_levels: tuple[str, ...] = ("stable", "lossy")) -> SurvivalExperiment:
    return SurvivalExperiment(
        experiment_id="manifest:v26.9.25",
        scenarios=(
            SurvivalScenario(
                scenario_id="world",
                subject="git:seanchatmangpt/gymact@0123456789abcdef",
                workload_id="sha256:manifest-workload",
                horizon=5,
                terminal_predicate_ref="urn:predicate:done",
            ),
        ),
        policies=(
            SurvivalPolicy(
                policy_id="formal",
                machinery=Machinery.FORMAL_GENERATED,
            ),
        ),
        factors=(
            SurvivalFactor(name="transport", levels=transport_levels),
            SurvivalFactor(name="authority", levels=("full", "filtered")),
        ),
        repetitions=2,
        seed_base=200,
    )


def test_manifest_freezes_every_manufactured_case_and_replays_exactly() -> None:
    source = experiment()
    manifest = build_survival_manifest(source)

    assert len(manifest.cases) == source.case_count == 8
    assert len({case.case_id for case in manifest.cases}) == 8
    assert manifest.authority == "none"
    assert manifest.actuation_performed is False
    assert len(manifest.manifest_digest) == 64

    replay = replay_survival_manifest(source, manifest)

    assert replay.matched is True
    assert replay.mismatches == ()
    assert replay.manifest_digest == replay.replay_digest


def test_manifest_replay_detects_experiment_and_case_graph_drift() -> None:
    original = experiment()
    manifest = build_survival_manifest(original)
    changed = experiment(transport_levels=("stable", "lossy", "partitioned"))

    replay = replay_survival_manifest(changed, manifest)

    assert replay.matched is False
    assert "EXPERIMENT_DIGEST_MISMATCH" in replay.mismatches
    assert "CASE_COUNT_MISMATCH" in replay.mismatches
    assert any(item.startswith("CASE_EXTRA:") for item in replay.mismatches)
    assert replay.manifest_digest != replay.replay_digest


def test_manifest_json_includes_digest_without_mutating_manifest_identity() -> None:
    manifest = build_survival_manifest(experiment())

    document = manifest.to_json()

    assert document["manifest_digest"] == manifest.manifest_digest
    assert document["schema_version"] == "gymact.survival-manifest/1"
    assert document["authority"] == "none"
    assert document["actuation_performed"] is False
