from dataclasses import dataclass

from .errors import Refused

@dataclass(frozen=True, slots=True)
class ObservedAlternative:
    candidate: str
    realized_loss: float
    observed: bool = True


def observed_regret(chosen: ObservedAlternative, alternatives: tuple[ObservedAlternative, ...]) -> float:
    if not chosen.observed:
        raise Refused("UNOBSERVED_CHOSEN_OUTCOME")
    observed = tuple(item for item in alternatives if item.observed)
    if len(observed) != len(alternatives):
        raise Refused("UNOBSERVED_COUNTERFACTUAL")
    if any(item.realized_loss < 0 for item in (chosen, *observed)):
        raise Refused("INVALID_REALIZED_LOSS")
    benchmark = min((chosen.realized_loss, *(item.realized_loss for item in observed)))
    return chosen.realized_loss - benchmark
