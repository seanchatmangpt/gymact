"""Bounded provider-local failover."""
from .envelope import Envelope
def failover(registry,e):
    if e.attempt>=e.max_attempts:raise RuntimeError("attempt_budget_exhausted")
    registry.exclude(e.candidate.provider); out=registry.select(e)
    return Envelope(out.candidate,e.attempt+1,e.max_attempts,"candidate")
