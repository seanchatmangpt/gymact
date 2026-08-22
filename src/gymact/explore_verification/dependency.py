def topo(edges: dict[str, set[str]]):
    pending = {key: set(value) for key, value in edges.items()}
    out = []
    while pending:
        ready = sorted(key for key, value in pending.items() if not (value & pending.keys()))
        if not ready:
            raise ValueError("REFUSED_DEPENDENCY_CYCLE")
        for key in ready:
            out.append(key)
            pending.pop(key)
    return tuple(out)
