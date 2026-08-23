from .observation import Observation
from .window import Window


def admit(
    observations: list[Observation], subject_sha: str, window: Window
) -> tuple[Observation, ...]:
    out = []
    seen = {}
    for observation in observations:
        if observation.subject.sha != subject_sha:
            raise ValueError("REFUSED_FOREIGN_SUBJECT")
        if not window.contains(observation.observed_at):
            continue
        key = (observation.kind, observation.observed_at)
        if key in seen and seen[key] != observation.outcome:
            raise ValueError("REFUSED_CONTRADICTORY_OBSERVATION")
        seen[key] = observation.outcome
        out.append(observation)
    return tuple(out)
