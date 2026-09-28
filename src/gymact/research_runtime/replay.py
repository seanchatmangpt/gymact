"""Bounded runtime primitive for ALOOP/survival/RACaP research."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class ReplayKey:
    subject: str
        policy_digest: str
        observation_digest: str
