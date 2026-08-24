from enum import StrEnum

from .refusal import FederationRefusal


class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def require_authority(action: ActionClass, broker: str | None = None) -> None:
    if action is ActionClass.DO and broker != "BRCE":
        raise FederationRefusal("UNRECEIPTED_ACTUATION")
