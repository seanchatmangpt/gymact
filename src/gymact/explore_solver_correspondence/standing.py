from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .refusal import Refused


@dataclass(frozen=True)
class Standing:
    state: str
    cost_gap: Fraction
    effective_evidence: Fraction


def qualify(
    *,
    cost_gap: Fraction,
    effective_evidence: Fraction,
    minimum: Fraction,
    dependency_states: tuple[str, ...],
) -> Standing:
    failure_states = {"BLOCKED", "BUILD_BROKEN", "REFUSED", "UNSUPPORTED"}
    if any(state in failure_states for state in dependency_states):
        return Standing("BUILD_BROKEN", cost_gap, effective_evidence)
    if cost_gap != 0:
        return Standing("UNSUPPORTED", cost_gap, effective_evidence)
    if effective_evidence < minimum:
        raise Refused("PSEUDO_QUORUM")
    return Standing("ALIVE", cost_gap, effective_evidence)
