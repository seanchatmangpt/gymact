"""Exact observation closure for manufactured survival campaigns.

Experiment-level observation closure expects one document per run case. A
fault campaign intentionally has multiple variants per run case, so campaign
closure keys evidence by campaign_case_id and separately verifies run-case and
fault-plan identities.
"""

from __future__ import annotations

from collections import Counter
from typing import Mapping, Sequence

from pydantic import Field

from gymact.models import FrozenModel
from gymact.survival_campaign import SurvivalCampaign


class SurvivalCampaignObservationClosure(FrozenModel):
    schema_version: str = "gymact.survival-campaign-observation-closure/1"
    campaign_digest: str = Field(min_length=64, max_length=64)
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


def qualify_campaign_observation_closure(
    campaign: SurvivalCampaign,
    documents: Sequence[Mapping[str, object]],
) -> SurvivalCampaignObservationClosure:
    """Require every campaign variant exactly once with exact campaign identity."""

    expected_by_id = {case.campaign_case_id: case for case in campaign.cases}
    observed_ids: list[str] = []
    drift: list[str] = []

    for document in documents:
        episode_id = str(document.get("episode_id", "")).strip() or "<missing-episode-id>"
        observed_ids.append(episode_id)
        expected = expected_by_id.get(episode_id)

        gymact = document.get("gymact")
        if not isinstance(gymact, Mapping):
            drift.append(episode_id)
            continue
        if expected is None:
            continue

        expected_fault_id = (
            expected.fault_plan.plan_id if expected.fault_plan is not None else None
        )
        if (
            str(gymact.get("campaign_id", "")) != campaign.campaign_id
            or str(gymact.get("campaign_spec_digest", "")) != campaign.spec_digest
            or str(gymact.get("run_case_id", "")) != expected.run_case.case_id
            or gymact.get("fault_plan_id") != expected_fault_id
            or bool(gymact.get("synthetic")) is not True
            or str(document.get("policy_id", ""))
            != expected.run_case.analysis_policy_id
        ):
            drift.append(episode_id)

    counts = Counter(observed_ids)
    observed = set(observed_ids)
    expected_ids = set(expected_by_id)
    missing = tuple(sorted(expected_ids - observed))
    unknown = tuple(sorted(observed - expected_ids))
    duplicates = tuple(
        sorted(case_id for case_id, count in counts.items() if count > 1)
    )
    drift_ids = tuple(sorted(set(drift)))
    complete = not (missing or unknown or duplicates or drift_ids)

    return SurvivalCampaignObservationClosure(
        campaign_digest=campaign.campaign_digest,
        expected_case_count=len(expected_ids),
        observed_unique_case_count=len(observed & expected_ids),
        missing_case_ids=missing,
        unknown_case_ids=unknown,
        duplicate_case_ids=duplicates,
        identity_drift_episode_ids=drift_ids,
        complete=complete,
        standing="STRUCTURAL" if complete else "PARTIAL",
    )


__all__ = [
    "SurvivalCampaignObservationClosure",
    "qualify_campaign_observation_closure",
]
