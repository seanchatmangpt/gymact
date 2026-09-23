from collections import Counter
from itertools import pairwise


def directly_follows(traces: tuple[tuple[str, ...], ...]) -> dict[tuple[str, str], int]:
    edges = Counter()
    for trace in traces:
        edges.update(pairwise(trace))
    return dict(sorted(edges.items()))
