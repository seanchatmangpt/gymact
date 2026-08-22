from __future__ import annotations

from dataclasses import dataclass

from .attempt import RecoveryAttempt
from .subject import Refusal


@dataclass(frozen=True, slots=True)
class AttemptFrontier:
    current: RecoveryAttempt | None
    historical: tuple[RecoveryAttempt, ...]


def resolve(attempts: list[RecoveryAttempt]) -> AttemptFrontier:
    if not attempts:
        return AttemptFrontier(None, ())
    max_ordinal = max(attempt.ordinal for attempt in attempts)
    maxima = [attempt for attempt in attempts if attempt.ordinal == max_ordinal]
    identities = {attempt.identity for attempt in maxima}
    if len(identities) > 1:
        raise Refusal("REFUSED_DIVERGENT_RECOVERY_FRONTIER")
    current = maxima[0]
    historical = tuple(
        sorted(
            (attempt for attempt in attempts if attempt.identity != current.identity),
            key=lambda attempt: (attempt.ordinal, attempt.identity),
        )
    )
    return AttemptFrontier(current, historical)
