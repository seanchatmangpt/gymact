from .authority import ActionClass, require
from .receipt import issue
from .standing import resolve
from .storage import select
from .strategies import evaluate, pareto

def qualify_regime(*, subject, regime, evidence_outcomes, drift, cusum_alarm, blockers=(), durable=False, transactional=False):
    require(ActionClass.CONSTRUCT)
    results=tuple(evaluate(s,drift=drift,cusum_alarm=cusum_alarm,support=8) for s in ("WINDOW_L1","PREQUENTIAL_CUSUM","MINIMAX_CURRENT"))
    frontier=pareto(results)
    standing=resolve(regime_state=regime.state,evidence_outcomes=evidence_outcomes,blockers=blockers)
    store=select(durable=durable,transactional=transactional)
    receipt=issue({"subject":f"{subject.repo}@{subject.sha}","generation":regime.generation,"regime_state":regime.state,"strategies":[r.strategy for r in frontier],"standing":standing.value,"store":store.kind.value})
    return standing, frontier, store, receipt
