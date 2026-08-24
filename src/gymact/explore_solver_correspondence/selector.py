from __future__ import annotations

from dataclasses import dataclass
from .capability import Capability
from .refusal import Refused

@dataclass(frozen=True)
class Selection:
    policy: str
    capability: Capability


def select(capabilities: tuple[Capability, ...], policy: str) -> Selection:
    if not capabilities:
        raise Refused("NO_CAPABILITY")
    if policy == "prefer-independent":
        ordered = sorted(capabilities, key=lambda c: ("independent" not in c.semantic, c.semantic))
    elif policy == "prefer-oracle":
        ordered = sorted(capabilities, key=lambda c: ("oracle" not in c.semantic, c.semantic))
    elif policy == "prefer-primal":
        ordered = sorted(capabilities, key=lambda c: ("primal" not in c.semantic, c.semantic))
    else:
        raise Refused("UNKNOWN_SELECTION_POLICY", policy)
    return Selection(policy, ordered[0])
