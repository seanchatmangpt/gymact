from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class IdempotencyRecord:
    key: str
    semantic_digest: str
    result_digest: str


def admit(records: list[IdempotencyRecord]) -> dict[str, IdempotencyRecord]:
    out: dict[str, IdempotencyRecord] = {}
    for record in records:
        prior = out.get(record.key)
        if prior and (prior.semantic_digest != record.semantic_digest or prior.result_digest != record.result_digest):
            raise ValueError("REFUSED[IDEMPOTENCY_COLLISION]")
        out[record.key] = record
    return out
