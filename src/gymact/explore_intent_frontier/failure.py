from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
from .context import SelectionContext

def inject(context: SelectionContext, seed: int, mode: str) -> SelectionContext:
    token=sha256(f"{seed}:{mode}:{context.fingerprint}".encode()).hexdigest()
    if mode=="cut":
        return replace(context, cut_id=f"{context.cut_id}-fault-{token[:8]}", cut_generation=context.cut_generation+1)
    if mode=="strategy":
        return replace(context, strategy=f"{context.strategy}-fault-{token[:8]}")
    if mode=="policy":
        return replace(context, policy_digest=token)
    if mode=="none":
        return context
    raise ValueError("REFUSED_UNKNOWN_FAILURE_MODE")
