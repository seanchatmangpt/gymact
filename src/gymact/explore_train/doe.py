from itertools import product


def full_factorial(factors: dict[str, tuple[object, ...]]) -> tuple[dict[str, object], ...]:
    keys = tuple(sorted(factors))
    if any(not factors[k] for k in keys):
        raise ValueError("REFUSED_EMPTY_FACTOR_LEVEL")
    return tuple(dict(zip(keys, values)) for values in product(*(factors[k] for k in keys)))
