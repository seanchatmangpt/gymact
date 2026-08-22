from __future__ import annotations
from .candidates import Candidate, lawful_candidates

def select_candidate(*, require_durable: bool = False, require_transactional: bool = False) -> Candidate:
    viable = [c for c in lawful_candidates() if (c.durable or not require_durable) and (c.transactional or not require_transactional)]
    if not viable:
        raise ValueError("REFUSED_NO_LAWFUL_CANDIDATE")
    return sorted(viable, key=lambda c: (c.transactional, c.durable, c.name))[0]
