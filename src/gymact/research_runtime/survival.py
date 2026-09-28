"""Bounded runtime primitive for ALOOP/survival/RACaP research."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class SurvivalScore:
    completed: int = 0
        failed: int = 0
        recovered: int = 0
