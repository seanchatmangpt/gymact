from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from .cascade import CascadeItem
from .event import InvalidationEvent

SCHEMA = "gymact.explore-invalidation/1"

@dataclass(frozen=True)
class Receipt:
    schema: str
    digest: str
    payload: dict[str, object]

def make_receipt(event: InvalidationEvent, items: tuple[CascadeItem, ...], standing: str) -> Receipt:
    payload: dict[str, object] = {
        "producer": event.producer.identity,
        "kind": event.kind,
        "observed_at": event.observed_at.isoformat(),
        "cascade": [{"binding_id": i.binding.binding_id, "consumer": i.binding.consumer.identity, "depth": i.depth, "reason": i.reason} for i in items],
        "standing": standing,
        "actuation_performed": False,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return Receipt(SCHEMA, hashlib.sha256(raw).hexdigest(), payload)
