from .candidates import Candidate
def pareto(cands:tuple[Candidate,...])->tuple[Candidate,...]:
    return tuple(sorted(cands,key=lambda c:(not c.durable,c.name)))
def select(cands:tuple[Candidate,...])->Candidate:
    if not cands: raise ValueError('REFUSED_NO_REVERSIBLE_CANDIDATE')
    return pareto(cands)[0]
