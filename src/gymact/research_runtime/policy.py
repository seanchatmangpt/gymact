"""Bounded runtime primitive for ALOOP/survival/RACaP research."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class RuntimePolicy:
    ordered_edges: tuple[str, ...]
        max_attempts: int = 3
