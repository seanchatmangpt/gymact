from __future__ import annotations

from enum import Enum

from .refusal import Refused

class Action(str, Enum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"

def admit(action: Action, broker: str | None = None) -> None:
    if action is Action.DO and broker != "BRCE":
        raise Refused("DO_REQUIRES_BRCE")
