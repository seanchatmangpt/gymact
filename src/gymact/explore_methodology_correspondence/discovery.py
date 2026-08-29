from collections import Counter

def directly_follows(traces: tuple[tuple[str,...],...]) -> dict[tuple[str,str],int]:
    edges=Counter()
    for trace in traces:
        edges.update(zip(trace,trace[1:]))
    return dict(sorted(edges.items()))
