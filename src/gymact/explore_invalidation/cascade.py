from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from .event import InvalidationEvent
from .graph import DependencyGraph
from .impact import direct_impact
from .model import Binding, Subject

@dataclass(frozen=True)
class CascadeItem:
    binding: Binding
    depth: int
    reason: str

def cascade(graph: DependencyGraph, event: InvalidationEvent) -> tuple[CascadeItem, ...]:
    queue = deque([(event.producer, 0)])
    seen: set[Subject] = {event.producer}
    out: list[CascadeItem] = []
    while queue:
        subject, depth = queue.popleft()
        for binding in graph.outgoing(subject):
            impact = direct_impact(binding, event)
            out.append(CascadeItem(binding, depth + 1, impact.reason))
            if binding.consumer not in seen:
                seen.add(binding.consumer)
                queue.append((binding.consumer, depth + 1))
    return tuple(sorted(out, key=lambda i: (i.depth, i.binding.binding_id)))
