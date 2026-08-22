from dataclasses import dataclass

@dataclass(frozen=True)
class PughResult:
    name: str
    score: int


def select(scores: dict[str, dict[str, int]], weights: dict[str, int]) -> PughResult:
    if not scores:
        raise ValueError("REFUSED_EMPTY_CANDIDATE_SET")
    ranked = []
    for name, criteria in scores.items():
        ranked.append(PughResult(name, sum(criteria.get(k, 0) * w for k, w in weights.items())))
    return max(ranked, key=lambda r: (r.score, r.name))
