from .epoch import Epoch
from .witness import Witness
_ORDER={"DELIVERY":0,"ACK":1,"DISCHARGE":2}
def admit(epoch:Epoch, witnesses:list[Witness])->tuple[Witness,...]:
    by_id={}
    for w in sorted(witnesses,key=lambda x:(x.consumer,x.observed_at,x.kind,x.witness_id)):
        if w.generation < epoch.generation: raise ValueError("REFUSED[STALE_INVALIDATION_EPOCH]")
        if w.generation > epoch.generation: raise ValueError("REFUSED[FUTURE_INVALIDATION_EPOCH]")
        if w.event_id != epoch.event_id: raise ValueError("REFUSED[EVENT_MISMATCH]")
        if w.kind!="DELIVERY":
            parent=by_id.get(w.parent_id or "")
            if parent is None or parent.consumer!=w.consumer or _ORDER[parent.kind]+1!=_ORDER[w.kind]:
                raise ValueError("REFUSED[CAUSAL_GAP]")
            if w.observed_at < parent.observed_at: raise ValueError("REFUSED[CAUSAL_TIME_REGRESSION]")
        by_id[w.witness_id]=w
    return tuple(by_id.values())
