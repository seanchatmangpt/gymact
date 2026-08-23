from collections import defaultdict
from fractions import Fraction
from typing import Iterable

from .logged import LoggedDecision
from .refusal import Refused


def total_variation(decisions: Iterable[LoggedDecision]) -> Fraction:
    rows = tuple(decisions)
    if not rows:
        raise Refused("REFUSED_EMPTY_LOG")
    behavior: dict[str, Fraction] = defaultdict(Fraction)
    target: dict[str, Fraction] = defaultdict(Fraction)
    for row in rows:
        behavior[row.action] += row.behavior_probability
        target[row.action] += row.target_probability
    behavior_total = sum(behavior.values(), Fraction())
    target_total = sum(target.values(), Fraction())
    if behavior_total == 0 or target_total == 0:
        raise Refused("REFUSED_ZERO_POLICY_MASS")
    actions = set(behavior) | set(target)
    distance = sum(
        (
            abs(behavior[action] / behavior_total - target[action] / target_total)
            for action in actions
        ),
        Fraction(),
    )
    return distance / 2
