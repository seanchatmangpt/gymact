ALLOWED={"OBSERVE","SELECT","CONSTRUCT","VERIFY"}
def require(action:str)->str:
    if action=="DO": raise PermissionError("REFUSED_UNRECEIPTED_ACTUATION")
    if action not in ALLOWED: raise PermissionError("REFUSED[UNKNOWN_AUTHORITY]")
    return action
