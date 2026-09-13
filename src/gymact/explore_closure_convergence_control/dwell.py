from __future__ import annotations

from datetime import timedelta

from .state import ObligationState
from .trajectory import ClosureEpoch


def stable_dwell(
    epochs: tuple[ClosureEpoch, ...], key: str, target: ObligationState
) -> timedelta:
    started = None
    ended = None
    for epoch in reversed(epochs):
        state = next(item.state for item in epoch.obligations if item.key == key)
        if state != target:
            break
        started = epoch.observed_at
        if ended is None:
            ended = epoch.observed_at
    if started is None or ended is None:
        return timedelta(0)
    return ended - started
