from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .intent import SelectionIntent


@dataclass(frozen=True, slots=True)
class IntentFrontier:
    current: SelectionIntent | None
    historical: tuple[SelectionIntent, ...]


def resolve(intents: tuple[SelectionIntent, ...], now: datetime) -> IntentFrontier:
    active = [i for i in intents if i.active(now)]
    if not active:
        return IntentFrontier(None, tuple(sorted(intents, key=lambda x: (x.issued_at, x.nonce))))
    latest = max(i.issued_at for i in active)
    maxima = [i for i in active if i.issued_at == latest]
    fingerprints = {i.context.fingerprint for i in maxima}
    if len(fingerprints) > 1:
        raise ValueError("REFUSED_DIVERGENT_INTENT_FRONTIER")
    current = sorted(maxima, key=lambda x: x.nonce)[0]
    historical = tuple(
        sorted((i for i in intents if i is not current), key=lambda x: (x.issued_at, x.nonce))
    )
    return IntentFrontier(current, historical)
