from __future__ import annotations

from .event import Event
from .trace import Trace


def collapse_adjacent_duplicates(trace: Trace) -> Trace:
    out: list[Event] = []
    for event in trace.events:
        if not out or out[-1].semantic_key != event.semantic_key:
            out.append(event)
    return Trace(trace.subject, trace.engine, tuple(out))


def project_activities(trace: Trace) -> tuple[str, ...]:
    return tuple(event.activity for event in trace.events)
