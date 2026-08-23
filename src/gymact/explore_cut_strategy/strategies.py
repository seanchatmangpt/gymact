from dataclasses import dataclass
from enum import Enum
from .cut import EvidenceCut
from .epoch import ProducerEpoch

class CutStrategy(str, Enum):
    LATEST_COMPLETE = "LATEST_COMPLETE"
    MAX_FRESHNESS = "MAX_FRESHNESS"
    MIN_SKEW = "MIN_SKEW"

@dataclass(frozen=True)
class ScoredCut:
    cut: EvidenceCut
    freshness: int
    skew: int

def score_cut(cut: EvidenceCut, current: dict[str, ProducerEpoch]) -> ScoredCut:
    gens=[e.generation for e in cut.epochs]
    freshness=sum(e.generation for e in cut.epochs if e.subject.repo in current)
    skew=(max(gens)-min(gens)) if gens else 0
    return ScoredCut(cut, freshness, skew)

def select_cut(cuts: tuple[EvidenceCut, ...], current: dict[str, ProducerEpoch], strategy: CutStrategy) -> EvidenceCut:
    if not cuts:
        raise ValueError("REFUSED_NO_CUT_CANDIDATES")
    scored=[score_cut(c,current) for c in cuts]
    if strategy is CutStrategy.LATEST_COMPLETE:
        return max(scored, key=lambda x:(x.cut.generation,x.cut.cut_id)).cut
    if strategy is CutStrategy.MAX_FRESHNESS:
        return max(scored, key=lambda x:(x.freshness,x.cut.generation,x.cut.cut_id)).cut
    return min(scored, key=lambda x:(x.skew,-x.freshness,x.cut.cut_id)).cut
