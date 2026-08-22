from __future__ import annotations

from math import prod


def ahp_priority(matrix: tuple[tuple[float, ...], ...]) -> tuple[float, ...]:
    size = len(matrix)
    if size == 0 or any(len(row) != size for row in matrix):
        raise ValueError("REFUSED_INVALID_AHP_MATRIX")
    if any(value <= 0 for row in matrix for value in row):
        raise ValueError("REFUSED_NONPOSITIVE_AHP_VALUE")
    roots = [prod(row) ** (1 / size) for row in matrix]
    total = sum(roots)
    return tuple(value / total for value in roots)
