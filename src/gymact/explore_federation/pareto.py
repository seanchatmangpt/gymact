def frontier(scores: dict[str, tuple[float, ...]]) -> tuple[str, ...]:
    ids = sorted(scores)
    output = []
    for candidate_id in ids:
        candidate = scores[candidate_id]
        dominated = False
        for other_id in ids:
            if candidate_id == other_id:
                continue
            other = scores[other_id]
            pairs = tuple(zip(other, candidate, strict=True))
            if all(left >= right for left, right in pairs) and any(
                left > right for left, right in pairs
            ):
                dominated = True
                break
        if not dominated:
            output.append(candidate_id)
    return tuple(output)
