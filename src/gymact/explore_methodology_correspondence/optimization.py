from dataclasses import dataclass
from fractions import Fraction

@dataclass(frozen=True)
class Candidate:
    name: str
    fitness: Fraction
    cost: Fraction

def frontier(items: tuple[Candidate,...]) -> tuple[Candidate,...]:
    def dominates(a: Candidate,b: Candidate) -> bool:
        return a.fitness>=b.fitness and a.cost<=b.cost and (a.fitness>b.fitness or a.cost<b.cost)
    return tuple(i for i in items if not any(j!=i and dominates(j,i) for j in items))
