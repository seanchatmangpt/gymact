from collections.abc import Callable
from time import perf_counter_ns


def run(candidates: dict[str, Callable[[dict], object]], payload: dict) -> tuple[dict, ...]:
    rows = []
    for name in sorted(candidates):
        start = perf_counter_ns()
        value = candidates[name](dict(payload))
        elapsed = perf_counter_ns() - start
        rows.append({"candidate": name, "elapsed_ns": elapsed, "value": value})
    return tuple(rows)
