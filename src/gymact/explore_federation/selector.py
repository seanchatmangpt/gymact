from .pareto import frontier


def select(
    scores: dict[str, tuple[float, ...]], blocked: set[str] = frozenset()
) -> tuple[str, tuple[str, ...]]:
    live = {key: value for key, value in scores.items() if key not in blocked}
    if not live:
        raise ValueError("REFUSED_NO_VIABLE_CANDIDATE")
    candidates = frontier(live)
    return candidates[0], candidates
