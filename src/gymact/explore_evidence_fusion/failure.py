import random
def inject_family_correlation(observations, seed:int, probability:float):
    if not 0<=probability<=1: raise ValueError("REFUSED_INVALID_FAILURE_PROBABILITY")
    rng=random.Random(seed); affected=set()
    for o in sorted(observations,key=lambda x:x.evidence_id):
        if rng.random()<probability: affected.add(o.source.family)
    return tuple(sorted(affected))
