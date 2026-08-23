from dataclasses import dataclass
from .cut import EvidenceCut
from .epoch import ProducerEpoch
from .strategies import CutStrategy, select_cut, score_cut

@dataclass(frozen=True)
class StrategyResult:
    strategy: CutStrategy
    cut_id: str
    freshness: int
    skew: int

def compare_strategies(cuts: tuple[EvidenceCut, ...], current: dict[str, ProducerEpoch]) -> tuple[StrategyResult, ...]:
    out=[]
    for strategy in CutStrategy:
        cut=select_cut(cuts,current,strategy)
        score=score_cut(cut,current)
        out.append(StrategyResult(strategy,cut.cut_id,score.freshness,score.skew))
    return tuple(out)

def pareto(results: tuple[StrategyResult, ...]) -> tuple[StrategyResult, ...]:
    keep=[]
    for r in results:
        dominated=any((o.freshness >= r.freshness and o.skew <= r.skew) and (o.freshness > r.freshness or o.skew < r.skew) for o in results)
        if not dominated:
            keep.append(r)
    return tuple(keep)
