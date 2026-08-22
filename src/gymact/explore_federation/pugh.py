def rank(
    matrix: dict[str, dict[str, float]], weights: dict[str, float]
) -> tuple[tuple[str, float], ...]:
    scored = [
        (
            candidate_id,
            sum(values.get(key, 0.0) * weight for key, weight in weights.items()),
        )
        for candidate_id, values in matrix.items()
    ]
    return tuple(sorted(scored, key=lambda row: (-row[1], row[0])))
