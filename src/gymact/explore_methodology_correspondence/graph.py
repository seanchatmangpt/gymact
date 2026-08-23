from collections import deque
from .witness import Witness

def shortest_path(edges: list[Witness], source: str, target: str, obligations: frozenset[str]) -> tuple[Witness, ...]:
    q=deque([(source,())]); seen={source}
    while q:
        node,path=q.popleft()
        if node==target: return path
        for e in edges:
            if e.source==node and e.preserves(obligations) and e.target not in seen:
                seen.add(e.target); q.append((e.target,path+(e,)))
    raise ValueError('REFUSED_NO_CORRESPONDENCE_PATH')
