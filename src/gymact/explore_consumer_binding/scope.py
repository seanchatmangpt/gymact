_ORDER={'FOCUSED':0,'INTEGRATION':1,'REPOSITORY':2}
def scope_satisfies(witness:str, required:str)->bool:
    if witness not in _ORDER or required not in _ORDER: raise ValueError('REFUSED_UNKNOWN_SCOPE')
    return _ORDER[witness]>=_ORDER[required]
