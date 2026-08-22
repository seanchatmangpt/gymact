from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from .compatibility import CompatibilityKind, CompatibilityWitness, admit_witness
from .context import SelectionContext
from .drift import DriftKind, classify

class FreshnessStrategy(StrEnum):
    RESELECT="RESELECT"
    REBIND_EQUIVALENT="REBIND_EQUIVALENT"
    REQUALIFY_COMPATIBLE="REQUALIFY_COMPATIBLE"

@dataclass(frozen=True, slots=True)
class FreshnessDecision:
    strategy: FreshnessStrategy
    reusable: bool
    standing: str
    reason: str

def decide(strategy: FreshnessStrategy, before: SelectionContext, after: SelectionContext,
           witness: CompatibilityWitness | None = None) -> FreshnessDecision:
    drift=classify(before, after)
    if drift.kind is DriftKind.UNCHANGED:
        return FreshnessDecision(strategy, True, "PARTIAL_ALIVE", "UNCHANGED_CONTEXT")
    if strategy is FreshnessStrategy.RESELECT:
        return FreshnessDecision(strategy, False, "REQUALIFYING", "CONTEXT_DRIFT_REQUIRES_RESELECT")
    if witness is None:
        return FreshnessDecision(strategy, False, "UNKNOWN", "MISSING_COMPATIBILITY_WITNESS")
    admit_witness(before, after, witness)
    if strategy is FreshnessStrategy.REBIND_EQUIVALENT:
        ok=witness.kind in {CompatibilityKind.EXACT, CompatibilityKind.SEMANTIC_EQUIVALENT}
        return FreshnessDecision(strategy, ok, "PARTIAL_ALIVE" if ok else "REQUALIFYING",
                                 "EQUIVALENT_REBIND" if ok else "NON_EQUIVALENT_REQUIRES_REQUALIFICATION")
    return FreshnessDecision(strategy, False, "REQUALIFYING", "COMPATIBLE_BUT_REQUALIFICATION_REQUIRED")
