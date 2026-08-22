from .observation import Observation
from .window import Window

def admit(observations:list[Observation], subject_sha:str, window:Window)->tuple[Observation,...]:
    out=[]; seen={}
    for o in observations:
        if o.subject.sha != subject_sha:
            raise ValueError("REFUSED_FOREIGN_SUBJECT")
        if not window.contains(o.observed_at):
            continue
        key=(o.kind,o.observed_at)
        if key in seen and seen[key] != o.outcome:
            raise ValueError("REFUSED_CONTRADICTORY_OBSERVATION")
        seen[key]=o.outcome; out.append(o)
    return tuple(out)
