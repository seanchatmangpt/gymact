from fractions import Fraction

from .logged import LoggedDecision
from .refusal import Refused


def importance_weight(decision: LoggedDecision) -> Fraction:
    if decision.behavior_probability <= 0:
        raise Refused("REFUSED_POSITIVITY_VIOLATION", decision.decision_id)
    return decision.target_probability / decision.behavior_probability


def clipped_weight(decision: LoggedDecision, limit: Fraction) -> Fraction:
    if limit <= 0:
        raise Refused("REFUSED_INVALID_WEIGHT_CLIP", str(limit))
    return min(importance_weight(decision), limit)
