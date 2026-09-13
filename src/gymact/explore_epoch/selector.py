from __future__ import annotations

from .stores import StoreCandidate, discover


def select_store(*, durable: bool, transactional: bool, candidates: tuple[StoreCandidate, ...] | None = None) -> StoreCandidate:
    pool = candidates or discover()
    viable = [c for c in pool if (not durable or c.durable) and (not transactional or c.transactional) and c.reversible]
    if not viable:
        raise ValueError("REFUSED_NO_REVERSIBLE_STORE_CANDIDATE")
    return sorted(viable, key=lambda c: (c.durable, c.transactional, c.kind.value))[0]
