from dataclasses import dataclass
from fractions import Fraction

@dataclass(frozen=True)
class StrategyResult:
    strategy: str
    accept: bool
    score: Fraction
    requalify: bool

def evaluate(strategy, *, drift, cusum_alarm, support):
    if strategy=="WINDOW_L1":
        return StrategyResult(strategy, drift < Fraction(1,2), Fraction(1)-min(Fraction(1),drift), drift>=Fraction(1,2))
    if strategy=="PREQUENTIAL_CUSUM":
        return StrategyResult(strategy, not cusum_alarm, Fraction(0 if cusum_alarm else 1), cusum_alarm)
    if strategy=="MINIMAX_CURRENT":
        risk=max(drift, Fraction(1, support or 1))
        return StrategyResult(strategy, risk < Fraction(1,2), Fraction(1)-min(Fraction(1),risk), risk>=Fraction(1,2))
    raise ValueError("unknown strategy")

def pareto(results):
    return tuple(r for r in results if not any(
        (o.score>=r.score and int(not o.requalify)>=int(not r.requalify)) and (o.score>r.score or o.requalify!=r.requalify)
        for o in results if o is not r
    ))
