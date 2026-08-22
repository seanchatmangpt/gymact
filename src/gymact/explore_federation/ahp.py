import math

def geometric_priority(rows:dict[str,tuple[float,...]])->tuple[tuple[str,float],...]:
    raw={k:(math.prod(v)**(1/len(v))) for k,v in rows.items() if v}
    total=sum(raw.values())
    if total<=0: raise ValueError("REFUSED_INVALID_AHP")
    return tuple(sorted(((k,v/total) for k,v in raw.items()),key=lambda x:(-x[1],x[0])))
