from __future__ import annotations

from collections.abc import Iterable

from .observation import Observation
from .subject import Subject
from .window import ObservationWindow


def admit_observations(
    subject: Subject,
    window: ObservationWindow,
    observations: Iterable[Observation],
) -> tuple[Observation, ...]:
    admitted: list[Observation] = []
    seen: dict[tuple[str, str], str] = {}
    for observation in observations:
        if observation.subject != subject:
            raise ValueError("REFUSED_FOREIGN_SUBJECT_OBSERVATION")
        if not window.contains(observation.observed_at):
            raise ValueError("REFUSED_OUT_OF_WINDOW_OBSERVATION")
        key = (observation.axis, observation.source)
        prior = seen.get(key)
        if prior is not None and prior != observation.outcome:
            raise ValueError("REFUSED_CONTRADICTORY_OBSERVATION")
        seen[key] = observation.outcome
        admitted.append(observation)
    return tuple(sorted(admitted, key=lambda item: (item.axis, item.source, item.observed_at)))
