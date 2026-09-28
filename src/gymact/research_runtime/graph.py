"""Bounded runtime primitive for ALOOP/survival/RACaP research."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class RuntimeGraph:
    edges: tuple[str, ...] = ()
        excluded: frozenset[str] = frozenset()
