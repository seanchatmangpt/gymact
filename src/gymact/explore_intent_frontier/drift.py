from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .context import SelectionContext


class DriftKind(StrEnum):
    UNCHANGED = "UNCHANGED"
    CUT = "CUT_CHANGED"
    STRATEGY = "STRATEGY_CHANGED"
    POLICY = "POLICY_CHANGED"
    MULTIPLE = "MULTIPLE_CONTEXT_CHANGES"


@dataclass(frozen=True, slots=True)
class Drift:
    kind: DriftKind
    fields: tuple[str, ...]


def classify(before: SelectionContext, after: SelectionContext) -> Drift:
    if before.subject != after.subject:
        raise ValueError("REFUSED_FOREIGN_CONTEXT_SUBJECT")
    changed = []
    if (before.cut_id, before.cut_digest, before.cut_generation) != (
        after.cut_id,
        after.cut_digest,
        after.cut_generation,
    ):
        changed.append("cut")
    if before.strategy != after.strategy:
        changed.append("strategy")
    if before.policy_digest != after.policy_digest:
        changed.append("policy")
    if not changed:
        kind = DriftKind.UNCHANGED
    elif len(changed) > 1:
        kind = DriftKind.MULTIPLE
    else:
        kind = {"cut": DriftKind.CUT, "strategy": DriftKind.STRATEGY, "policy": DriftKind.POLICY}[
            changed[0]
        ]
    return Drift(kind, tuple(changed))
