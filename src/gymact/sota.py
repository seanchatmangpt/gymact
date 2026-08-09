"""Standing-qualified SOTA comparison primitives.

A benchmark score is not admitted into a frontier until its subject and
experiment identities are bound to replayable receipt evidence.  This module
is deliberately small: it provides the 80/20 comparison algebra without
pretending that GymAct can establish external SOTA by itself.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite


class SotaAdmissionError(ValueError):
    """Typed refusal for a result that cannot enter SOTA comparison."""


@dataclass(frozen=True, slots=True)
class StandingEvidence:
    """Minimum crown evidence required before comparative optimization."""

    subject_digest: str
    experiment_digest: str
    receipt_digest: str
    verifier_digest: str
    replay_verified: bool

    def admit(self) -> None:
        bindings = {
            "subject": self.subject_digest,
            "experiment": self.experiment_digest,
            "receipt": self.receipt_digest,
            "verifier": self.verifier_digest,
        }
        missing = sorted(name for name, value in bindings.items() if not value.strip())
        if missing:
            raise SotaAdmissionError(f"REFUSED:SOTA_MISSING_BINDING:{','.join(missing)}")
        if not self.replay_verified:
            raise SotaAdmissionError("REFUSED:SOTA_REPLAY_NOT_VERIFIED")


@dataclass(frozen=True, slots=True)
class FrontierResult:
    """One standing-qualified result in a declared metric space.

    Metrics are normalized so larger is always better.  Cost/latency callers
    therefore negate or otherwise normalize those dimensions explicitly.
    """

    result_id: str
    evidence: StandingEvidence
    metrics: Mapping[str, float]

    def admit(self) -> None:
        if not self.result_id.strip():
            raise SotaAdmissionError("REFUSED:SOTA_EMPTY_RESULT_ID")
        self.evidence.admit()
        if not self.metrics:
            raise SotaAdmissionError("REFUSED:SOTA_EMPTY_METRICS")
        for name, value in self.metrics.items():
            if not name.strip() or not isfinite(float(value)):
                raise SotaAdmissionError("REFUSED:SOTA_INVALID_METRIC")


def _same_metric_space(left: FrontierResult, right: FrontierResult) -> tuple[str, ...]:
    left_keys = tuple(sorted(left.metrics))
    right_keys = tuple(sorted(right.metrics))
    if left_keys != right_keys:
        raise SotaAdmissionError("REFUSED:SOTA_METRIC_SPACE_MISMATCH")
    return left_keys


def dominates(left: FrontierResult, right: FrontierResult) -> bool:
    """Return whether left Pareto-dominates right after both are admitted."""
    left.admit()
    right.admit()
    keys = _same_metric_space(left, right)
    weakly_better = all(left.metrics[key] >= right.metrics[key] for key in keys)
    strictly_better = any(left.metrics[key] > right.metrics[key] for key in keys)
    return weakly_better and strictly_better


def pareto_frontier(results: Iterable[FrontierResult]) -> tuple[FrontierResult, ...]:
    """Return the deterministic nondominated frontier of admitted results."""
    admitted = tuple(results)
    if not admitted:
        return ()
    for result in admitted:
        result.admit()
    reference = admitted[0]
    for result in admitted[1:]:
        _same_metric_space(reference, result)
    frontier = [
        candidate
        for candidate in admitted
        if not any(
            challenger.result_id != candidate.result_id and dominates(challenger, candidate)
            for challenger in admitted
        )
    ]
    return tuple(sorted(frontier, key=lambda result: result.result_id))


def sota_claim(candidate: FrontierResult, comparison_set: Iterable[FrontierResult]) -> bool:
    """Admit a bounded SOTA claim iff no admitted comparator dominates candidate.

    This establishes only a claim relative to the supplied comparison set and
    metric space.  It intentionally does not manufacture a universal SOTA
    claim from local benchmark evidence.
    """
    candidate.admit()
    comparators = tuple(comparison_set)
    for comparator in comparators:
        comparator.admit()
        _same_metric_space(candidate, comparator)
    return not any(dominates(comparator, candidate) for comparator in comparators)
