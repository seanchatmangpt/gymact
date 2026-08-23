from .selectors import Candidate


def dominates(a: Candidate, b: Candidate) -> bool:
    weak = a.risk <= b.risk and a.support >= b.support and a.shift <= b.shift and a.ess >= b.ess
    strict = a.risk < b.risk or a.support > b.support or a.shift < b.shift or a.ess > b.ess
    return weak and strict


def frontier(candidates: list[Candidate]) -> list[Candidate]:
    return [
        candidate
        for candidate in candidates
        if not any(dominates(other, candidate) for other in candidates if other != candidate)
    ]
