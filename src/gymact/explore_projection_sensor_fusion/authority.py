from enum import StrEnum

from .refusals import FusionRefused


class ActionClass(StrEnum):
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    DO = "DO"


def require_authority(action: ActionClass) -> None:
    if action is ActionClass.DO:
        raise FusionRefused("REFUSED_UNRECEIPTED_ACTUATION")
