def pareto(scores: dict[str, dict[str, float]]):
    names = sorted(scores)
    keep = []
    for left in names:
        dominated = False
        for right in names:
            if left == right:
                continue
            keys = set(scores[left]) | set(scores[right])
            not_worse = all(
                scores[right].get(key, float("-inf")) >= scores[left].get(key, float("-inf"))
                for key in keys
            )
            better = any(
                scores[right].get(key, float("-inf")) > scores[left].get(key, float("-inf"))
                for key in keys
            )
            if not_worse and better:
                dominated = True
                break
        if not dominated:
            keep.append(left)
    return tuple(keep)
