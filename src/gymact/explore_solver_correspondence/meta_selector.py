from __future__ import annotations

from dataclasses import dataclass
from .selector import Selection, select
from .capability import Capability
from .refusal import Refused

@dataclass(frozen=True)
class MetaSelection:
    objective: str
    selection: Selection


def meta_select(capabilities: tuple[Capability, ...], objective: str) -> MetaSelection:
    policy = {"epistemic-independence": "prefer-independent", "bounded-exhaustiveness": "prefer-oracle", "scalability": "prefer-primal"}.get(objective)
    if policy is None:
        raise Refused("UNKNOWN_META_OBJECTIVE", objective)
    return MetaSelection(objective, select(capabilities, policy))
