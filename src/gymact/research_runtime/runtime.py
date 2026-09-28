"""Bounded runtime primitive for ALOOP/survival/RACaP research."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    max_attempts: int = 3
        queue_limit: int = 128
        epoch_limit: int = 100
