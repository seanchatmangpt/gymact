from .epoch import Epoch
def current_epoch(epochs:list[Epoch])->Epoch:
    if not epochs: raise ValueError("REFUSED[NO_EPOCH]")
    top=max(e.generation for e in epochs)
    current=[e for e in epochs if e.generation==top]
    keys={(e.event_id,e.receipt) for e in current}
    if len(keys)!=1: raise ValueError("REFUSED[DIVERGENT_EPOCH_FRONTIER]")
    return sorted(current,key=lambda e:e.observed_at)[-1]
