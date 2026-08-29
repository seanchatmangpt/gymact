from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .refusal import Refused

@dataclass
class Edge:
    to: int
    rev: int
    capacity: Fraction
    cost: Fraction
    initial: Fraction

@dataclass(frozen=True)
class FlowResult:
    cost: Fraction
    flow: Fraction
    edge_flows: tuple[tuple[int, int, Fraction], ...]

class MinCostFlow:
    """Exact rational successive shortest augmenting paths with residual rerouting."""

    def __init__(self, n: int) -> None:
        if n <= 0:
            raise Refused("INVALID_FLOW_GRAPH")
        self.graph: list[list[Edge]] = [[] for _ in range(n)]

    def add_edge(self, u: int, v: int, capacity: Fraction, cost: Fraction) -> None:
        if capacity < 0:
            raise Refused("NEGATIVE_CAPACITY")
        if u == v:
            raise Refused("SELF_FLOW_EDGE")
        fwd = Edge(v, len(self.graph[v]), capacity, cost, capacity)
        rev = Edge(u, len(self.graph[u]), Fraction(), -cost, Fraction())
        self.graph[u].append(fwd)
        self.graph[v].append(rev)

    def solve(self, source: int, sink: int, required: Fraction) -> FlowResult:
        if required < 0:
            raise Refused("NEGATIVE_REQUIRED_FLOW")
        total = Fraction()
        total_cost = Fraction()
        n = len(self.graph)
        while total < required:
            dist: list[Fraction | None] = [None] * n
            prev: list[tuple[int, int] | None] = [None] * n
            dist[source] = Fraction()
            for _ in range(n - 1):
                changed = False
                for u in range(n):
                    if dist[u] is None:
                        continue
                    for idx, edge in enumerate(self.graph[u]):
                        if edge.capacity <= 0:
                            continue
                        nd = dist[u] + edge.cost
                        if dist[edge.to] is None or nd < dist[edge.to]:
                            dist[edge.to] = nd
                            prev[edge.to] = (u, idx)
                            changed = True
                if not changed:
                    break
            if dist[sink] is None:
                raise Refused("INSUFFICIENT_FLOW_CAPACITY")
            amount = required - total
            v = sink
            while v != source:
                step = prev[v]
                if step is None:
                    raise Refused("BROKEN_AUGMENTING_PATH")
                u, idx = step
                amount = min(amount, self.graph[u][idx].capacity)
                v = u
            v = sink
            while v != source:
                step = prev[v]
                if step is None:
                    raise Refused("BROKEN_AUGMENTING_PATH")
                u, idx = step
                edge = self.graph[u][idx]
                edge.capacity -= amount
                self.graph[v][edge.rev].capacity += amount
                v = u
            total += amount
            total_cost += amount * dist[sink]
        used = []
        for u, edges in enumerate(self.graph):
            for edge in edges:
                if edge.initial > 0:
                    sent = edge.initial - edge.capacity
                    if sent:
                        used.append((u, edge.to, sent))
        return FlowResult(total_cost, total, tuple(used))
