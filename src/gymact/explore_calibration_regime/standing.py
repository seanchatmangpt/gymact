from enum import Enum
class Standing(str,Enum):
    UNKNOWN="UNKNOWN"; PARTIAL_ALIVE="PARTIAL_ALIVE"; BUILD_BROKEN="BUILD_BROKEN"; BLOCKED="BLOCKED"; REQUALIFYING="REQUALIFYING"
def resolve(*, regime_state, evidence_outcomes, blockers=()):
    if blockers: return Standing.BLOCKED
    if "FAIL" in evidence_outcomes: return Standing.BUILD_BROKEN
    if regime_state=="DRIFT": return Standing.REQUALIFYING
    if regime_state=="INSUFFICIENT": return Standing.UNKNOWN
    return Standing.PARTIAL_ALIVE if "PASS" in evidence_outcomes else Standing.UNKNOWN
