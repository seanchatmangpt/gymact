from itertools import product


def full_factorial(factors: dict[str, tuple]) -> tuple[dict, ...]:
    keys = tuple(sorted(factors))
    return tuple(
        dict(zip(keys, values, strict=True)) for values in product(*(factors[key] for key in keys))
    )
