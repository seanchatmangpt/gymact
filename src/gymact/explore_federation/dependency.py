def topo(edges: dict[str, set[str]]) -> tuple[str, ...]:
    temporary = set()
    done = set()
    output = []

    def visit(node: str) -> None:
        if node in temporary:
            raise ValueError("REFUSED_DEPENDENCY_CYCLE")
        if node in done:
            return
        temporary.add(node)
        for dependency in sorted(edges.get(node, set())):
            visit(dependency)
        temporary.remove(node)
        done.add(node)
        output.append(node)

    for node in sorted(edges):
        visit(node)
    return tuple(output)
