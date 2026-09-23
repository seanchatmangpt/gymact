from dataclasses import dataclass

from .admission import admit
from .clusters import correlated_clusters
from .diversity import inverse_simpson_effective_size
from .pareto import pareto_frontier
from .receipt import issue
from .storage import select
from .strategies import Strategy, evaluate


@dataclass(frozen=True)
class Qualification:
    standing: str
    selected_strategy: Strategy
    frontier: tuple
    receipt: object


def qualify(
    *,
    subject,
    observations,
    graph,
    now,
    independent_pairs=frozenset(),
    durable=True,
    transactional=False,
    requested_action="CONSTRUCT",
):
    if requested_action == "DO":
        raise PermissionError("REFUSED_UNRECEIPTED_ACTUATION")
    admitted = admit(observations, subject, now)
    clusters = correlated_clusters(admitted, graph, independent_pairs)
    div = inverse_simpson_effective_size(clusters)
    decisions = tuple(evaluate(s, clusters, div) for s in Strategy)
    frontier = pareto_frontier(decisions)
    chosen = next((d for d in frontier if d.strategy is Strategy.MINIMAX_FAILURE), frontier[0])
    store = select(durable=durable, transactional=transactional)
    rec = issue(subject, chosen.strategy, chosen.standing, len(clusters), div, store)
    return Qualification(chosen.standing, chosen.strategy, frontier, rec)
