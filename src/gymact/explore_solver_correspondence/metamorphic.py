from __future__ import annotations

from dataclasses import dataclass

from .refusal import Refused


@dataclass(frozen=True)
class MetamorphicEvidence:
    baseline_digest: str
    transformed_digest: str
    cost_preserved: bool


def require_cost_invariance(baseline: object, transformed: object) -> MetamorphicEvidence:
    ok = baseline.result.cost == transformed.result.cost
    if not ok:
        raise Refused("METAMORPHIC_COST_DIVERGENCE")
    return MetamorphicEvidence(baseline.result.digest, transformed.result.digest, True)
