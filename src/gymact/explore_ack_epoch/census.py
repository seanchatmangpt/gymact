from .witness import Witness
def census(consumers:list[str], witnesses:tuple[Witness,...])->dict[str,str]:
    by={c:[] for c in sorted(set(consumers))}
    for w in witnesses:
        if w.consumer in by: by[w.consumer].append(w.kind)
    out={}
    for c,kinds in by.items():
        s=set(kinds)
        out[c]="DISCHARGED" if "DISCHARGE" in s else "ACKED" if "ACK" in s else "DELIVERED" if "DELIVERY" in s else "PENDING"
    return out
