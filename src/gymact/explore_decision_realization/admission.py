from collections.abc import Iterable

from .decision import DecisionIdentity
from .errors import Refused
from .outcome import RealizedOutcome


def admit_outcomes(decision: DecisionIdentity, outcomes: Iterable[RealizedOutcome]) -> tuple[RealizedOutcome, ...]:
    admitted: list[RealizedOutcome] = []
    seen: dict[str, RealizedOutcome] = {}
    for outcome in outcomes:
        outcome.bind(decision)
        prior = seen.get(outcome.outcome_id)
        if prior is not None:
            if prior != outcome:
                raise Refused("CONTRADICTORY_DUPLICATE_OUTCOME", outcome.outcome_id)
            raise Refused("DUPLICATE_OUTCOME", outcome.outcome_id)
        seen[outcome.outcome_id] = outcome
        admitted.append(outcome)
    if not admitted:
        raise Refused("NO_REALIZATION_EVIDENCE")
    return tuple(sorted(admitted, key=lambda item: (item.observed_at_ns, item.outcome_id)))
