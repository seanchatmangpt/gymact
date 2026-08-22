from __future__ import annotations
from .event import InvalidationEvent
from .graph import DependencyGraph
from .model import Refusal

def admit_event(graph: DependencyGraph, event: InvalidationEvent) -> InvalidationEvent:
    producers = {b.producer for b in graph.bindings}
    if event.producer not in producers:
        raise Refusal("REFUSED_ORPHAN_INVALIDATION_EVENT")
    return event
