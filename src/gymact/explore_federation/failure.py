def inject(value, *, fail:bool=False, code:str="INJECTED_FAILURE"):
    if fail: raise RuntimeError(code)
    return value
