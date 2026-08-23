from __future__ import annotations

from collections import defaultdict

from .state import ObligationState
from .trajectory import ClosureEpoch


def oscillating_obligations(epochs: tuple[ClosureEpoch, ...]) -> frozenset[str]:
    history: dict[str, list[ObligationState]] = defaultdict(list)
    for epoch in epochs:
        for item in epoch.obligations:
            history[item.key].append(item.state)
    oscillating: set[str] = set()
    for key, states in history.items():
        compressed = [states[0]]
        for state in states[1:]:
            if state != compressed[-1]:
                compressed.append(state)
        if len(compressed) >= 3 and compressed[0] == compressed[-1]:
            oscillating.add(key)
        elif len(compressed) >= 4:
            oscillating.add(key)
    return frozenset(oscillating)
