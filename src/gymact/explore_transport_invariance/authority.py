from __future__ import annotations

from enum import StrEnum

from .refusal import Refusal


class Action(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def require_authority(action: Action, broker: str | None = None) -> None:
    if action is Action.DO and broker != "BRCE":
        raise Refusal("UNRECEIPTED_ACTUATION", "consequential DO requires BRCE")
