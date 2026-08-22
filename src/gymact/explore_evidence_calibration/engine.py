from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from .admission import admit
from .compare import pareto,vector
from .contracts import Refusal,Subject
from .dependencies import blockers
from .estimate import CalibrationEstimate
from .receipt import QualificationReceipt,issue
from .sequential import SequentialDecision,decide
from .storage import StoreCandidate,select
from .strategies import FusionResult,FusionStrategy,evaluate
from .witness import CurrentWitness,EvidenceCluster
@dataclass(frozen=True)
class Qualification:
    decision:SequentialDecision; selected_strategy:FusionStrategy; store:StoreCandidate; frontier:tuple[str,...]; blockers:tuple[str,...]; receipt:QualificationReceipt

def qualify(subject:Subject,clusters:tuple[EvidenceCluster,...],witnesses:tuple[CurrentWitness,...],estimates:tuple[CalibrationEstimate,...],*,now:datetime,dependency_edges:dict[str,tuple[str,...]],dependency_standings:dict[str,str],dependency_root:str,transactional:bool=False)->Qualification:
    _,estimate_map=admit(subject,clusters,witnesses,estimates,now=now)
    dep_blockers=blockers(dependency_edges,dependency_standings,dependency_root)
    results:tuple[FusionResult,...]=tuple(evaluate(s,witnesses,estimate_map) for s in FusionStrategy)
    frontier=pareto(tuple(vector(r) for r in results))
    chosen=next(r for r in results if r.strategy is (FusionStrategy.MINIMAX_UNDER_SUPPORT if any(r.under_calibrated for r in results) else FusionStrategy.CALIBRATED_LOG_ODDS))
    decision=decide(chosen)
    if dep_blockers: decision=SequentialDecision(decision.decision,"BLOCKED",decision.score)
    store=select(durable=True,transactional=transactional)
    receipt=issue({"subject":subject.exact_id,"strategy":chosen.strategy.value,"standing":decision.standing,"score":decision.score,"store":store.kind.value,"frontier":[v.strategy for v in frontier],"blockers":list(dep_blockers)})
    return Qualification(decision,chosen.strategy,store,tuple(v.strategy for v in frontier),dep_blockers,receipt)

def require_do()->None: raise Refusal("REFUSED_UNRECEIPTED_ACTUATION")
