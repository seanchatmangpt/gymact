from __future__ import annotations

from enum import Enum

from .migration import MigrationDecision, MigrationDisposition


class Compatibility(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    REQUALIFY = "REQUALIFY"
    BLOCKED = "BLOCKED"


def classify(decisions: tuple[MigrationDecision, ...]) -> Compatibility:
    if any(d.disposition is MigrationDisposition.BLOCK for d in decisions):
        return Compatibility.BLOCKED
    if any(d.disposition is MigrationDisposition.REQUALIFY for d in decisions):
        return Compatibility.REQUALIFY
    return Compatibility.COMPATIBLE
