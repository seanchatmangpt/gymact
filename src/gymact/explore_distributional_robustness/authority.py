from __future__ import annotations

from enum import StrEnum

from .refusals import refuse


class Action(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def admit_action(action: Action, broker: str | None = None) -> Action:
    if action is Action.DO and broker != "BRCE":
        raise refuse("UNRECEIPTED_ACTUATION", "consequential DO requires BRCE")
    return action
