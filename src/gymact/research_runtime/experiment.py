"""Bounded runtime primitive for ALOOP/survival/RACaP research."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class ExperimentCase:
    case_id: str
        seed: int
        fault: str | None = None
