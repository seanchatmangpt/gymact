from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from .logged import LoggedDecision
from .refusal import Refused


@dataclass(frozen=True, slots=True)
class SupportSummary:
    observations: int
    target_supported: int
    target_mass: Fraction
    support_ratio: Fraction


def require_target_action_support(
    behavior_actions: Iterable[str], target_actions: Iterable[str]
) -> None:
    observed = set(behavior_actions)
    missing = sorted(set(target_actions) - observed)
    if missing:
        raise Refused("REFUSED_TARGET_ACTION_OUT_OF_SUPPORT", ",".join(missing))


def summarize(decisions: Iterable[LoggedDecision]) -> SupportSummary:
    rows = tuple(decisions)
    if not rows:
        raise Refused("REFUSED_EMPTY_LOG")
    supported = sum(row.target_probability > 0 for row in rows)
    target_mass = sum((row.target_probability for row in rows), Fraction())
    return SupportSummary(
        observations=len(rows),
        target_supported=supported,
        target_mass=target_mass,
        support_ratio=Fraction(supported, len(rows)),
    )
