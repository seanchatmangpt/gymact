from dataclasses import dataclass

from .errors import Refused

@dataclass(frozen=True, slots=True)
class CUSUMState:
    positive: float = 0.0
    negative: float = 0.0


def update(state: CUSUMState, observed_loss: float, target_loss: float, slack: float, threshold: float) -> tuple[CUSUMState, bool]:
    if min(observed_loss, target_loss, slack, threshold) < 0 or threshold == 0:
        raise Refused("INVALID_DRIFT_PARAMETER")
    residual = observed_loss - target_loss
    positive = max(0.0, state.positive + residual - slack)
    negative = min(0.0, state.negative + residual + slack)
    next_state = CUSUMState(positive, negative)
    return next_state, positive >= threshold or abs(negative) >= threshold
