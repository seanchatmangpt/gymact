from itertools import product


def full_factorial(
    factors: dict[str, tuple[object, ...]],
) -> tuple[dict[str, object], ...]:
    keys = tuple(sorted(factors))
    if any(not factors[key] for key in keys):
        raise ValueError("REFUSED_EMPTY_FACTOR_LEVEL")
    levels = product(*(factors[key] for key in keys))
    return tuple(dict(zip(keys, values, strict=True)) for values in levels)
