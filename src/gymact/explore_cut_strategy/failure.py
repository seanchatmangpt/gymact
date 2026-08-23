from dataclasses import replace
from random import Random
from .cut import EvidenceCut
from .epoch import ProducerEpoch

def advance_one(current: dict[str, ProducerEpoch], seed: int) -> dict[str, ProducerEpoch]:
    if not current:
        return {}
    rng=Random(seed)
    repo=sorted(current)[rng.randrange(len(current))]
    updated=dict(current)
    old=current[repo]
    updated[repo]=replace(old, generation=old.generation+1, receipt=f"{old.generation+1:064x}")
    return updated

def expire_cut(cut: EvidenceCut) -> EvidenceCut:
    return replace(cut, valid_until=cut.valid_from)
