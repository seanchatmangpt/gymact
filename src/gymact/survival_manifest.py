"""Content-addressed manifests for GymAct survival experiments.

A manifest freezes the manufactured case graph before execution. Replaying a
manifest means rebuilding the cases from the same experiment definition and
proving that every case identity, factor assignment, seed, and policy identity
matches. It does not execute a case and does not grant DO authority.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from gymact.evidence import digest
from gymact.models import FrozenModel
from gymact.survival_experiment import SurvivalExperiment, SurvivalRunCase


class SurvivalManifestCase(FrozenModel):
    case_id: str = Field(min_length=1)
    analysis_policy_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    repetition: int = Field(ge=0)
    seed: int = Field(ge=0)
    factor_digest: str = Field(min_length=64, max_length=64)

    @classmethod
    def from_case(cls, case: SurvivalRunCase) -> "SurvivalManifestCase":
        return cls(
            case_id=case.case_id,
            analysis_policy_id=case.analysis_policy_id,
            scenario_id=case.cell.scenario.scenario_id,
            policy_id=case.cell.policy.policy_id,
            repetition=case.repetition,
            seed=case.seed,
            factor_digest=case.factor_digest,
        )


class SurvivalExperimentManifest(FrozenModel):
    schema_version: Literal["gymact.survival-manifest/1"] = "gymact.survival-manifest/1"
    experiment_id: str = Field(min_length=1)
    experiment_digest: str = Field(min_length=64, max_length=64)
    cases: tuple[SurvivalManifestCase, ...]
    authority: Literal["none"] = "none"
    actuation_performed: Literal[False] = False

    @property
    def manifest_digest(self) -> str:
        return digest(self.model_dump(mode="json"))

    def to_json(self) -> dict[str, Any]:
        value = self.model_dump(mode="json")
        value["manifest_digest"] = self.manifest_digest
        return value


class SurvivalManifestReplay(FrozenModel):
    manifest_digest: str = Field(min_length=64, max_length=64)
    replay_digest: str = Field(min_length=64, max_length=64)
    matched: bool
    mismatches: tuple[str, ...]
    authority: Literal["none"] = "none"
    actuation_performed: Literal[False] = False


def experiment_digest(experiment: SurvivalExperiment) -> str:
    """Digest the declarative experiment definition, never runtime observations."""

    return digest(experiment.model_dump(mode="json"))


def build_survival_manifest(experiment: SurvivalExperiment) -> SurvivalExperimentManifest:
    cases = experiment.cases()
    return SurvivalExperimentManifest(
        experiment_id=experiment.experiment_id,
        experiment_digest=experiment_digest(experiment),
        cases=tuple(SurvivalManifestCase.from_case(case) for case in cases),
    )


def replay_survival_manifest(
    experiment: SurvivalExperiment,
    manifest: SurvivalExperimentManifest,
) -> SurvivalManifestReplay:
    """Re-manufacture the case graph and compare exact identities."""

    mismatches: list[str] = []
    current_experiment_digest = experiment_digest(experiment)
    if manifest.experiment_id != experiment.experiment_id:
        mismatches.append("EXPERIMENT_ID_MISMATCH")
    if manifest.experiment_digest != current_experiment_digest:
        mismatches.append("EXPERIMENT_DIGEST_MISMATCH")

    current_cases = tuple(
        SurvivalManifestCase.from_case(case) for case in experiment.cases()
    )
    if len(current_cases) != len(manifest.cases):
        mismatches.append("CASE_COUNT_MISMATCH")

    by_id = {case.case_id: case for case in manifest.cases}
    if len(by_id) != len(manifest.cases):
        mismatches.append("MANIFEST_CASE_ID_DUPLICATE")

    current_by_id = {case.case_id: case for case in current_cases}
    missing = sorted(set(by_id) - set(current_by_id))
    extra = sorted(set(current_by_id) - set(by_id))
    mismatches.extend(f"CASE_MISSING:{case_id}" for case_id in missing)
    mismatches.extend(f"CASE_EXTRA:{case_id}" for case_id in extra)

    for case_id in sorted(set(by_id) & set(current_by_id)):
        if by_id[case_id] != current_by_id[case_id]:
            mismatches.append(f"CASE_DRIFT:{case_id}")

    replay_payload = {
        "experiment_id": experiment.experiment_id,
        "experiment_digest": current_experiment_digest,
        "cases": [case.model_dump(mode="json") for case in current_cases],
    }
    return SurvivalManifestReplay(
        manifest_digest=manifest.manifest_digest,
        replay_digest=digest(replay_payload),
        matched=not mismatches,
        mismatches=tuple(mismatches),
    )


__all__ = [
    "SurvivalExperimentManifest",
    "SurvivalManifestCase",
    "SurvivalManifestReplay",
    "build_survival_manifest",
    "experiment_digest",
    "replay_survival_manifest",
]
