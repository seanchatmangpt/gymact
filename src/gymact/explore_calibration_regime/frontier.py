from .refusal import Refusal

def current_frontier(regimes):
    if not regimes: raise Refusal("REFUSED_EMPTY_REGIME_FRONTIER")
    max_gen=max(r.generation for r in regimes)
    current=[r for r in regimes if r.generation==max_gen]
    identities={(r.source_id,r.model_digest,r.state) for r in current}
    if len(identities)!=1: raise Refusal("REFUSED_DIVERGENT_REGIME_FRONTIER")
    chosen=current[0]
    history=tuple(r for r in regimes if r.generation<max_gen)
    return chosen, history
