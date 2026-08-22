from .authority import require
from .receipt import make
from .selector import select


def construct(
    scores: dict[str, tuple[float, ...]], blocked: set[str] = frozenset()
) -> dict:
    require("SELECT")
    winner, alternatives = select(scores, blocked)
    require("CONSTRUCT")
    plan = {"winner": winner, "alternatives": alternatives, "authority": "CONSTRUCT"}
    return {"plan": plan, "receipt": make(plan)}
