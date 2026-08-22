ALLOWED = {"OBSERVE", "SELECT", "CONSTRUCT", "VERIFY"}


def require(action: str) -> str:
    if action not in ALLOWED:
        raise PermissionError("REFUSED_UNRECEIPTED_ACTUATION")
    return action
