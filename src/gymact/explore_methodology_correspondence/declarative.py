from dataclasses import dataclass

@dataclass(frozen=True)
class Constraint:
    before: str
    after: str

def satisfies(trace: tuple[str, ...], constraints: tuple[Constraint, ...]) -> bool:
    pos={a:i for i,a in enumerate(trace)}
    return all(c.before in pos and c.after in pos and pos[c.before] < pos[c.after] for c in constraints)
