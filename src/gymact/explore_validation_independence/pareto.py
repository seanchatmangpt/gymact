from .selector import Candidate

def dominates(left: Candidate, right: Candidate) -> bool:
    no_worse = left.coverage >= right.coverage and left.width <= right.width and left.overlap <= right.overlap and left.cost <= right.cost
    strictly = left.coverage > right.coverage or left.width < right.width or left.overlap < right.overlap or left.cost < right.cost
    return no_worse and strictly

def frontier(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    return tuple(candidate for candidate in candidates if not any(dominates(other, candidate) for other in candidates if other is not candidate))
