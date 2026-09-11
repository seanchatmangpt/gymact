from dataclasses import dataclass

@dataclass(frozen=True)
class Intent:
    key: str
    operation: str
    payload: tuple[tuple[str, object], ...]


def admit_idempotency(seen: dict[str, Intent], intent: Intent) -> str:
    prior = seen.get(intent.key)
    if prior is None:
        seen[intent.key] = intent
        return "ADMITTED"
    if prior == intent:
        return "REPLAY"
    return "REFUSED_IDEMPOTENCY_COLLISION"


def test_same_key_same_intent_replays_but_changed_intent_refuses() -> None:
    seen: dict[str, Intent] = {}
    first = Intent("k1", "create", (("name", "x"),))
    changed = Intent("k1", "delete", (("name", "x"),))
    assert admit_idempotency(seen, first) == "ADMITTED"
    assert admit_idempotency(seen, first) == "REPLAY"
    assert admit_idempotency(seen, changed) == "REFUSED_IDEMPOTENCY_COLLISION"
