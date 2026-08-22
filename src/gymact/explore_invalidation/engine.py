from __future__ import annotations
from dataclasses import dataclass
from .admission import admit_event
from .cascade import CascadeItem, cascade
from .event import InvalidationEvent
from .graph import DependencyGraph
from .receipt import Receipt, make_receipt
from .selection import select_candidate
from .standing import affected_standing
from .model import Refusal

@dataclass(frozen=True)
class Qualification:
    standing: str
    candidate: str
    cascade: tuple[CascadeItem, ...]
    receipt: Receipt

def qualify(graph: DependencyGraph, event: InvalidationEvent, *, previous_standing: str = "PARTIAL_ALIVE") -> Qualification:
    admit_event(graph, event)
    items = cascade(graph, event)
    standing = affected_standing(previous_standing, event)
    candidate = select_candidate(require_durable=True)
    receipt = make_receipt(event, items, standing)
    return Qualification(standing, candidate.name, items, receipt)

def require_do() -> None:
    raise Refusal("REFUSED_UNRECEIPTED_ACTUATION")
