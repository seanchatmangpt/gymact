from dataclasses import dataclass
from enum import Enum
class Strategy(str,Enum):
    CLUSTER_MAJORITY="CLUSTER_MAJORITY"
    DIVERSITY_WEIGHTED="DIVERSITY_WEIGHTED"
    MINIMAX_FAILURE="MINIMAX_FAILURE"
@dataclass(frozen=True)
class Decision:
    strategy: Strategy
    standing: str
    score: tuple
    rationale: str
def _cluster_outcomes(clusters): return [{o.outcome for o in c} for c in clusters]
def evaluate(strategy,clusters,diversity):
    outs=_cluster_outcomes(clusters); fail=sum("FAIL" in x for x in outs); passed=sum(x=={"PASS"} for x in outs); unknown=len(outs)-fail-passed
    if fail: standing="BUILD_BROKEN"
    elif strategy is Strategy.MINIMAX_FAILURE and unknown: standing="UNKNOWN"
    elif passed>=2 and unknown==0: standing="PARTIAL_ALIVE"
    else: standing="UNKNOWN"
    if strategy is Strategy.CLUSTER_MAJORITY: score=(passed,-fail,-unknown)
    elif strategy is Strategy.DIVERSITY_WEIGHTED: score=(passed*diversity,-fail,-unknown)
    else: score=(-fail,-unknown,passed)
    return Decision(strategy,standing,score,f"clusters={len(clusters)} pass={passed} fail={fail} unknown={unknown}")
