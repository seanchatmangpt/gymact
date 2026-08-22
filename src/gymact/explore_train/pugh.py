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
        score = sum(criteria.get(key, 0) * weight for key, weight in weights.items())
        ranked.append(PughResult(name, score))
    return max(ranked, key=lambda result: (result.score, result.name))
