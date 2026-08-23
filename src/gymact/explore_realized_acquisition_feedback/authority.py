from enum import StrEnum

from .subject import Refusal


class ActionClass(StrEnum):
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    DO = "DO"


def require_action(action: ActionClass) -> None:
    if action is ActionClass.DO:
        raise Refusal("REFUSED_UNRECEIPTED_ACTUATION")
