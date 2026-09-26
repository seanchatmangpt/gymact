"""Paired-world evidence for champion/candidate capability evaluation.

GymAct owns the bounded executable world, not promotion policy.  This module
therefore manufactures replayable paired evidence only.  A downstream control
plane may consume that evidence to promote or reject a candidate, but these
objects grant no authority and do not perform production DO.
"""

from __future__ import annotations

from math import isfinite
from typing import Literal, Self

from blake3 import blake3
from pydantic import Field, model_validator

from gymact.evidence import digest
from gymact.models import FrozenModel

_CONTENT_DIGEST = r"^(?:sha256|blake3):[0-9a-f]{64}$"


class PairedWorldIdentity(FrozenModel):
    """Identity of the exact world/task/seed/budget/evaluator cohort cell."""

    world_digest: str = Field(pattern=_CONTENT_DIGEST)
    task_digest: str = Field(pattern=_CONTENT_DIGEST)
    seed: int
    budget_digest: str = Field(pattern=_CONTENT_DIGEST)
    evaluator_digest: str = Field(pattern=_CONTENT_DIGEST)

    @property
    def identity_digest(self) -> str:
        return "blake3:" + digest(self.model_dump(mode="json"))


class CapabilityObservation(FrozenModel):
    """One observed capability outcome in the bounded world."""

    capability_digest: str = Field(pattern=_CONTENT_DIGEST)
    outcome_digest: str = Field(pattern=_CONTENT_DIGEST)
    consequence_digest: str = Field(pattern=_CONTENT_DIGEST)
    receipt_digest: str = Field(pattern=_CONTENT_DIGEST)
    score: float
    success: bool
    steps: int = Field(ge=0)

    @model_validator(mode="after")
    def finite_score(self) -> Self:
        if not isfinite(self.score):
            raise ValueError("PAIRED_WORLD_NON_FINITE_SCORE")
        return self


class PairedWorldRun(FrozenModel):
    """Champion and candidate observations bound to one exact cohort identity."""

    identity: PairedWorldIdentity
    champion: CapabilityObservation
    candidate: CapabilityObservation
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def distinct_capabilities(self) -> Self:
        if self.champion.capability_digest == self.candidate.capability_digest:
            raise ValueError("PAIRED_WORLD_IDENTICAL_CAPABILITY")
        return self

    @property
    def pair_digest(self) -> str:
        return "blake3:" + digest(self.model_dump(mode="json"))


class PairedWorldEvidence(FrozenModel):
    """Replayable evidence projection; still not a promotion verdict."""

    identity_digest: str = Field(pattern=_CONTENT_DIGEST)
    pair_digest: str = Field(pattern=_CONTENT_DIGEST)
    champion_capability_digest: str = Field(pattern=_CONTENT_DIGEST)
    candidate_capability_digest: str = Field(pattern=_CONTENT_DIGEST)
    champion_score: float
    candidate_score: float
    delta: float
    champion_success: bool
    candidate_success: bool
    champion_receipt_digest: str = Field(pattern=_CONTENT_DIGEST)
    candidate_receipt_digest: str = Field(pattern=_CONTENT_DIGEST)
    evidence_digest: str = Field(pattern=_CONTENT_DIGEST)
    authority: Literal["none"] = "none"


class PairedWorldCohort(FrozenModel):
    """A same-capability-pair cohort with no duplicate world identities."""

    evidence: tuple[PairedWorldEvidence, ...]
    cohort_digest: str = Field(pattern=_CONTENT_DIGEST)
    authority: Literal["none"] = "none"


class PairedWorldCourt:
    """Manufacture paired evidence without deciding whether to promote."""

    def observe(self, run: PairedWorldRun) -> PairedWorldEvidence:
        payload = {
            "identity": run.identity.model_dump(mode="json"),
            "champion": run.champion.model_dump(mode="json"),
            "candidate": run.candidate.model_dump(mode="json"),
        }
        evidence_digest = "blake3:" + blake3(
            digest(payload).encode("ascii")
        ).hexdigest()
        return PairedWorldEvidence(
            identity_digest=run.identity.identity_digest,
            pair_digest=run.pair_digest,
            champion_capability_digest=run.champion.capability_digest,
            candidate_capability_digest=run.candidate.capability_digest,
            champion_score=run.champion.score,
            candidate_score=run.candidate.score,
            delta=run.candidate.score - run.champion.score,
            champion_success=run.champion.success,
            candidate_success=run.candidate.success,
            champion_receipt_digest=run.champion.receipt_digest,
            candidate_receipt_digest=run.candidate.receipt_digest,
            evidence_digest=evidence_digest,
        )

    def observe_cohort(self, runs: tuple[PairedWorldRun, ...]) -> PairedWorldCohort:
        if not runs:
            raise ValueError("PAIRED_WORLD_COHORT_EMPTY")

        identities = [run.identity.identity_digest for run in runs]
        if len(identities) != len(set(identities)):
            raise ValueError("PAIRED_WORLD_DUPLICATE_IDENTITY")

        champion_digests = {run.champion.capability_digest for run in runs}
        candidate_digests = {run.candidate.capability_digest for run in runs}
        if len(champion_digests) != 1 or len(candidate_digests) != 1:
            raise ValueError("PAIRED_WORLD_MIXED_CAPABILITY_PAIR")

        evidence = tuple(self.observe(run) for run in runs)
        cohort_payload = {
            "identity_digests": identities,
            "pair_digests": [item.pair_digest for item in evidence],
            "champion": next(iter(champion_digests)),
            "candidate": next(iter(candidate_digests)),
        }
        return PairedWorldCohort(
            evidence=evidence,
            cohort_digest="blake3:" + digest(cohort_payload),
        )
