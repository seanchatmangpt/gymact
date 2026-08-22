from __future__ import annotations

from dataclasses import dataclass

from .subject import Subject


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    upstream: Subject
    downstream: Subject


def topological(
    subjects: tuple[Subject, ...], edges: tuple[DependencyEdge, ...]
) -> tuple[Subject, ...]:
    nodes = {s.identity: s for s in subjects}
    incoming = {k: 0 for k in nodes}
    out = {k: [] for k in nodes}
    for e in edges:
        a, b = e.upstream.identity, e.downstream.identity
        if a not in nodes or b not in nodes:
            raise ValueError("REFUSED_UNKNOWN_DEPENDENCY_SUBJECT")
        if a == b:
            raise ValueError("REFUSED_DEPENDENCY_CYCLE")
        out[a].append(b)
        incoming[b] += 1
    ready = sorted(k for k, v in incoming.items() if v == 0)
    ordered = []
    while ready:
        n = ready.pop(0)
        ordered.append(nodes[n])
        for m in sorted(out[n]):
            incoming[m] -= 1
            if incoming[m] == 0:
                ready.append(m)
                ready.sort()
    if len(ordered) != len(nodes):
        raise ValueError("REFUSED_DEPENDENCY_CYCLE")
    return tuple(ordered)


def propagate_blockers(
    order: tuple[Subject, ...], edges: tuple[DependencyEdge, ...], standings: dict[str, str]
) -> dict[str, str]:
    result = dict(standings)
    for s in order:
        if result.get(s.identity) in {"BUILD_BROKEN", "BLOCKED"}:
            for e in edges:
                if e.upstream == s:
                    result[e.downstream.identity] = "BLOCKED"
    return result
