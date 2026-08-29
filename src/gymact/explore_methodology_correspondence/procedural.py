from dataclasses import dataclass

@dataclass(frozen=True)
class Transition:
    source: str; activity: str; target: str

def accepts(start: str, trace: tuple[str, ...], transitions: tuple[Transition, ...]) -> str:
    state=start
    for activity in trace:
        matches=[t for t in transitions if t.source==state and t.activity==activity]
        if len(matches)!=1: raise ValueError('REFUSED_NONDETERMINISTIC_OR_INVALID_TRACE')
        state=matches[0].target
    return state
