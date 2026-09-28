"""Bounded runtime primitive for ALOOP/survival/RACaP research."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class RuntimeReceipt:
    subject: str
        edge: str
        outcome: str
        authority: str = "none"
