from enum import StrEnum

from .refusal import Refusal, RefusalCode, refuse


class ActionClass(StrEnum):
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    DO = "DO"


def admit_action(action: ActionClass) -> Refusal | None:
    if action is ActionClass.DO:
        return refuse(RefusalCode.UNRECEIPTED_ACTUATION, "consequential DO requires BRCE authority")
    return None
