from __future__ import annotations

from enum import StrEnum

from .identity import Refused


class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def admit_action(action: ActionClass) -> ActionClass:
    if action is ActionClass.DO:
        raise Refused("REFUSED_UNRECEIPTED_ACTUATION")
    return action
