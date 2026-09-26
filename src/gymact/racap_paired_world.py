"""Paired-world evidence for champion/candidate capability evaluation.

GymAct owns the bounded executable world, not promotion policy.  This module
therefore manufactures replayable paired evidence only.  A downstream control
plane may consume that evidence to promote or reject a candidate, but these
objects grant no authority and do not perform production DO.
"""

from __future__ import annotations

from enum import StrEnum
from math import isfinite
from typing import Callable, Literal, Self

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

        ordered_runs = tuple(sorted(runs, key=lambda run: run.identity.identity_digest))
        identities = [run.identity.identity_digest for run in ordered_runs]
        if len(identities) != len(set(identities)):
            raise ValueError("PAIRED_WORLD_DUPLICATE_IDENTITY")

        champion_digests = {run.champion.capability_digest for run in ordered_runs}
        candidate_digests = {run.candidate.capability_digest for run in ordered_runs}
        if len(champion_digests) != 1 or len(candidate_digests) != 1:
            raise ValueError("PAIRED_WORLD_MIXED_CAPABILITY_PAIR")

        evidence = tuple(self.observe(run) for run in ordered_runs)
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



class PairedExecutionOrder(StrEnum):
    """Explicit order so execution-order effects are evidence, not hidden state."""

    CHAMPION_FIRST = "champion_first"
    CANDIDATE_FIRST = "candidate_first"


class PairedExecutionRecord(FrozenModel):
    """One executed pair plus order identity and its powerless evidence."""

    identity: PairedWorldIdentity
    order: PairedExecutionOrder
    run: PairedWorldRun
    evidence: PairedWorldEvidence
    execution_digest: str = Field(pattern=_CONTENT_DIGEST)
    authority: Literal["none"] = "none"


ObservationExecutor = Callable[[PairedWorldIdentity, str], CapabilityObservation]


class PairedWorldRunner:
    """Execute both capability versions against the same bounded world identity.

    The injected executor is responsible for materializing/resetting the bounded
    GymAct world for the supplied identity. This runner enforces that the
    observation returned by that executor is for the exact requested capability,
    preserves explicit execution order, and passes the result through the
    PairedWorldCourt. It has no production authority and no promotion policy.
    """

    def __init__(
        self,
        executor: ObservationExecutor,
        court: PairedWorldCourt | None = None,
    ) -> None:
        self.executor = executor
        self.court = court or PairedWorldCourt()

    def execute_pair(
        self,
        *,
        identity: PairedWorldIdentity,
        champion_capability_digest: str,
        candidate_capability_digest: str,
        order: PairedExecutionOrder = PairedExecutionOrder.CHAMPION_FIRST,
    ) -> PairedExecutionRecord:
        if champion_capability_digest == candidate_capability_digest:
            raise ValueError("PAIRED_WORLD_IDENTICAL_CAPABILITY")

        if order is PairedExecutionOrder.CHAMPION_FIRST:
            champion = self._execute(identity, champion_capability_digest)
            candidate = self._execute(identity, candidate_capability_digest)
        else:
            candidate = self._execute(identity, candidate_capability_digest)
            champion = self._execute(identity, champion_capability_digest)

        run = PairedWorldRun(
            identity=identity,
            champion=champion,
            candidate=candidate,
        )
        evidence = self.court.observe(run)
        execution_payload = {
            "identity_digest": identity.identity_digest,
            "order": order.value,
            "pair_digest": run.pair_digest,
            "evidence_digest": evidence.evidence_digest,
        }
        return PairedExecutionRecord(
            identity=identity,
            order=order,
            run=run,
            evidence=evidence,
            execution_digest="blake3:" + digest(execution_payload),
        )

    def execute_cohort(
        self,
        *,
        identities: tuple[PairedWorldIdentity, ...],
        champion_capability_digest: str,
        candidate_capability_digest: str,
        alternate_order: bool = True,
    ) -> PairedWorldCohort:
        if not identities:
            raise ValueError("PAIRED_WORLD_COHORT_EMPTY")

        records: list[PairedExecutionRecord] = []
        for index, identity in enumerate(identities):
            order = (
                PairedExecutionOrder.CANDIDATE_FIRST
                if alternate_order and index % 2
                else PairedExecutionOrder.CHAMPION_FIRST
            )
            records.append(
                self.execute_pair(
                    identity=identity,
                    champion_capability_digest=champion_capability_digest,
                    candidate_capability_digest=candidate_capability_digest,
                    order=order,
                )
            )

        return self.court.observe_cohort(tuple(record.run for record in records))

    def _execute(
        self,
        identity: PairedWorldIdentity,
        capability_digest: str,
    ) -> CapabilityObservation:
        observation = self.executor(identity, capability_digest)
        if observation.capability_digest != capability_digest:
            raise ValueError("PAIRED_WORLD_EXECUTOR_CAPABILITY_MISMATCH")
        return observation


class PairedCohortReplay(FrozenModel):
    """A replay manifest binding exact identities and resulting evidence."""

    identity_digests: tuple[str, ...]
    champion_capability_digest: str = Field(pattern=_CONTENT_DIGEST)
    candidate_capability_digest: str = Field(pattern=_CONTENT_DIGEST)
    evidence_digests: tuple[str, ...]
    cohort_digest: str = Field(pattern=_CONTENT_DIGEST)
    manifest_digest: str = Field(pattern=_CONTENT_DIGEST)
    authority: Literal["none"] = "none"

    @classmethod
    def from_cohort(cls, cohort: PairedWorldCohort) -> Self:
        ordered = tuple(sorted(cohort.evidence, key=lambda item: item.identity_digest))
        if not ordered:
            raise ValueError("PAIRED_WORLD_COHORT_EMPTY")
        champion = {item.champion_capability_digest for item in ordered}
        candidate = {item.candidate_capability_digest for item in ordered}
        if len(champion) != 1 or len(candidate) != 1:
            raise ValueError("PAIRED_WORLD_MIXED_CAPABILITY_PAIR")
        payload = {
            "identity_digests": [item.identity_digest for item in ordered],
            "champion": next(iter(champion)),
            "candidate": next(iter(candidate)),
            "evidence_digests": [item.evidence_digest for item in ordered],
            "cohort_digest": cohort.cohort_digest,
        }
        return cls(
            identity_digests=tuple(payload["identity_digests"]),
            champion_capability_digest=payload["champion"],
            candidate_capability_digest=payload["candidate"],
            evidence_digests=tuple(payload["evidence_digests"]),
            cohort_digest=cohort.cohort_digest,
            manifest_digest="blake3:" + digest(payload),
        )
