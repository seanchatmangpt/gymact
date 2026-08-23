from dataclasses import dataclass

from .contracts import CandidateContract


@dataclass(frozen=True)
class AdmissionRule:
    required_capabilities: frozenset[str]
    require_reversible: bool = True


@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    reason: str


def admit(candidate: CandidateContract, rule: AdmissionRule) -> AdmissionDecision:
    missing = rule.required_capabilities.difference(candidate.capabilities)
    if missing:
        reason = "REFUSED_MISSING_CAPABILITIES:" + ",".join(sorted(missing))
        return AdmissionDecision(False, reason)
    if rule.require_reversible and not candidate.reversible:
        return AdmissionDecision(False, "REFUSED_IRREVERSIBLE_CANDIDATE")
    return AdmissionDecision(True, "ADMITTED")
