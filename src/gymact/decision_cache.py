"""Refusal-aware semantic decision cache with zero cached execution authority."""
from __future__ import annotations

from pydantic import Field

from gymact.models import FrozenModel, Standing


class DecisionKey(FrozenModel):
    problem_identity: str = Field(min_length=1)
    environment_identity: str = Field(min_length=1)
    authority_class: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    subject_revision: str = Field(min_length=1)


class CandidateDecision(FrozenModel):
    key: DecisionKey
    candidate_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    standing: Standing = Standing.CANDIDATE


class RefusalDecision(FrozenModel):
    key: DecisionKey
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...]
    standing: Standing = Standing.REFUSED


class DecisionResolution(FrozenModel):
    standing: Standing
    candidate_refs: tuple[str, ...] = ()
    reason: str
    cache_hit: bool


class DecisionCache:
    """Cache candidates and lawful refusals only under exact semantic identity.

    No principal, authority reference, delegated identity, or ExecutionGrant can be
    stored. Authority is re-admitted later at BRCE for every consequential operation.
    """

    def __init__(self) -> None:
        self._candidates: dict[DecisionKey, CandidateDecision] = {}
        self._refusals: dict[DecisionKey, RefusalDecision] = {}

    def put_candidate(self, decision: CandidateDecision) -> None:
        if not decision.candidate_refs or not decision.evidence_refs:
            raise ValueError("CACHED_CANDIDATE_REQUIRES_EVIDENCE")
        self._refusals.pop(decision.key, None)
        self._candidates[decision.key] = decision

    def put_refusal(self, decision: RefusalDecision) -> None:
        if not decision.evidence_refs:
            raise ValueError("CACHED_REFUSAL_REQUIRES_EVIDENCE")
        self._candidates.pop(decision.key, None)
        self._refusals[decision.key] = decision

    def resolve(self, key: DecisionKey) -> DecisionResolution:
        refused = self._refusals.get(key)
        if refused is not None:
            return DecisionResolution(
                standing=Standing.REFUSED,
                reason=refused.reason,
                cache_hit=True,
            )
        candidate = self._candidates.get(key)
        if candidate is not None:
            return DecisionResolution(
                standing=Standing.CANDIDATE,
                candidate_refs=candidate.candidate_refs,
                reason="EXACT_CACHED_CANDIDATE_AUTHORITY_STILL_REQUIRED",
                cache_hit=True,
            )
        return DecisionResolution(
            standing=Standing.UNKNOWN,
            reason="NO_EXACT_DECISION_CACHE_ENTRY",
            cache_hit=False,
        )
