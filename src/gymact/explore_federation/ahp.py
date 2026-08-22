import math


def geometric_priority(rows: dict[str, tuple[float, ...]]) -> tuple[tuple[str, float], ...]:
    raw = {key: math.prod(values) ** (1 / len(values)) for key, values in rows.items() if values}
    total = sum(raw.values())
    if total <= 0:
        raise ValueError("REFUSED_INVALID_AHP")
    return tuple(
        sorted(((key, value / total) for key, value in raw.items()), key=lambda row: (-row[1], row[0]))
    )
