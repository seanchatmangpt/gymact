from dataclasses import dataclass

@dataclass(frozen=True)
class POWLNode:
    name: str
    successors: tuple[str, ...]

def bounded_reachable(nodes: tuple[POWLNode, ...], start: str, target: str, max_steps: int) -> bool:
    graph={n.name:n.successors for n in nodes}; frontier={(start,0)}; seen=set()
    while frontier:
        node,depth=frontier.pop()
        if node==target: return True
        if depth>=max_steps: continue
        key=(node,depth)
        if key in seen: continue
        seen.add(key)
        frontier.update((n,depth+1) for n in graph.get(node,()))
    return False
