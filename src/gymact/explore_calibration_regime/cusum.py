from dataclasses import dataclass
from fractions import Fraction
from .refusal import Refusal

@dataclass(frozen=True)
class CusumResult:
    positive: Fraction
    negative: Fraction
    alarm: bool

def detect(errors, *, target=Fraction(1,10), slack=Fraction(1,20), threshold=Fraction(1,2)):
    if threshold <= 0: raise Refusal("REFUSED_INVALID_CUSUM_THRESHOLD")
    pos=Fraction(0); neg=Fraction(0)
    for error in errors:
        x=Fraction(int(bool(error)),1)-target
        pos=max(Fraction(0), pos+x-slack)
        neg=min(Fraction(0), neg+x+slack)
    return CusumResult(pos,neg,pos>=threshold or -neg>=threshold)
