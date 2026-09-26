"""Exact manifest observation closure for GymAct survival runs.

This module detects missing, duplicate, unknown, and identity-drifted episode
documents against a pre-manufactured :class:`SurvivalExperimentManifest`.
Presence is structural evidence only; it is not semantic success.
"""

from __future__ import annotations

from collections import Counter
from typing import Mapping, Sequence

from pydantic import Field

from gymact.models import FrozenModel
from gymact.survival_manifest import SurvivalExperimentManifest


class SurvivalObservationClosure(FrozenModel):
    schema_version: str = "gymact.survival-observation-closure/1"
    manifest_digest: str = Field(min_length=64, max_length=64)
    expected_case_count: int = Field(ge=0)
    observed_unique_case_count: int = Field(ge=0)
    missing_case_ids: tuple[str, ...]
    unknown_case_ids: tuple[str, ...]
    duplicate_case_ids: tuple[str, ...]
    identity_drift_episode_ids: tuple[str, ...]
    complete: bool
    standing: str
    authority: str = "none"
    actuation_performed: bool = False


def qualify_observation_closure(
    manifest: SurvivalExperimentManifest,
    documents: Sequence[Mapping[str, object]],
) -> SurvivalObservationClosure:
    """Require every manifested case exactly once with exact bounded identity."""

    expected_by_id = {
        case.case_id: case
        for case in manifest.cases
    }
    observed_ids: list[str] = []
    drift: list[str] = []

    for document in documents:
        episode_id = str(document.get("episode_id", "")).strip() or "<missing-episode-id>"
        gymact = document.get("gymact")
        if not isinstance(gymact, Mapping):
            drift.append(episode_id)
            continue

        case_id = str(gymact.get("run_case_id", "")).strip()
        if not case_id:
            drift.append(episode_id)
            continue
        observed_ids.append(case_id)

        expected = expected_by_id.get(case_id)
        if expected is None:
            continue

        if (
            str(document.get("policy_id", "")) != expected.analysis_policy_id
            or str(gymact.get("scenario_id", "")) != expected.scenario_id
            or int(gymact.get("repetition", -1)) != expected.repetition
            or int(gymact.get("seed", -1)) != expected.seed
        ):
            drift.append(episode_id)

    counts = Counter(observed_ids)
    observed = set(observed_ids)
    expected = set(expected_by_id)
    missing = tuple(sorted(expected - observed))
    unknown = tuple(sorted(observed - expected))
    duplicates = tuple(
        sorted(case_id for case_id, count in counts.items() if count > 1)
    )
    drift_ids = tuple(sorted(set(drift)))
    complete = not (missing or unknown or duplicates or drift_ids)

    return SurvivalObservationClosure(
        manifest_digest=manifest.manifest_digest,
        expected_case_count=len(expected),
        observed_unique_case_count=len(observed & expected),
        missing_case_ids=missing,
        unknown_case_ids=unknown,
        duplicate_case_ids=duplicates,
        identity_drift_episode_ids=drift_ids,
        complete=complete,
        standing="STRUCTURAL" if complete else "PARTIAL",
    )


__all__ = ["SurvivalObservationClosure", "qualify_observation_closure"]
