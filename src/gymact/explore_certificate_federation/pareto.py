from .selectors import Candidate


def pareto_frontier(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    def dominates(a: Candidate, b: Candidate) -> bool:
        weak = (
            a.generation >= b.generation
            and a.runtime_diversity >= b.runtime_diversity
            and a.effective_evidence >= b.effective_evidence
            and a.cost <= b.cost
        )
        strict = (
            a.generation > b.generation
            or a.runtime_diversity > b.runtime_diversity
            or a.effective_evidence > b.effective_evidence
            or a.cost < b.cost
        )
        return weak and strict

    return tuple(c for c in candidates if not any(dominates(other, c) for other in candidates if other is not c))
