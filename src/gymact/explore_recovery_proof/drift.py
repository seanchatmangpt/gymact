from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .context import RecoveryContext


class DriftKind(StrEnum):
    NONE = "NONE"
    CUT = "CUT"
    STRATEGY = "STRATEGY"
    POLICY = "POLICY"
    GENERATION = "GENERATION"
    MULTI = "MULTI"


@dataclass(frozen=True, slots=True)
class Drift:
    kind: DriftKind
    axes: tuple[str, ...]


def classify(before: RecoveryContext, after: RecoveryContext) -> Drift:
    axes: list[str] = []
    if before.cut_id != after.cut_id:
        axes.append("cut")
    if before.strategy != after.strategy:
        axes.append("strategy")
    if before.policy_digest != after.policy_digest:
        axes.append("policy")
    if before.generation != after.generation:
        axes.append("generation")
    if not axes:
        return Drift(DriftKind.NONE, ())
    if len(axes) > 1:
        return Drift(DriftKind.MULTI, tuple(axes))
    return Drift(DriftKind(axes[0].upper()), tuple(axes))
