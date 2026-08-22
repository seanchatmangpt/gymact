from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import product


def full_factorial(factors: Mapping[str, Sequence[object]]) -> tuple[dict[str, object], ...]:
    names = tuple(sorted(factors))
    if not names or any(not factors[name] for name in names):
        raise ValueError("REFUSED_EMPTY_DOE_FACTOR")
    rows = []
    for values in product(*(factors[name] for name in names)):
        rows.append(dict(zip(names, values, strict=True)))
    return tuple(rows)
