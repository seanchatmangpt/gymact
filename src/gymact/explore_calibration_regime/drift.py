from dataclasses import dataclass
from fractions import Fraction
from .refusal import Refusal

@dataclass(frozen=True)
class DriftVector:
    tpr_delta: Fraction
    fpr_delta: Fraction
    brier_delta: Fraction
    l1: Fraction

def compare(old,new):
    if old.source_id != new.source_id: raise Refusal("REFUSED_FOREIGN_CALIBRATION_MODEL")
    a=abs(old.tpr-new.tpr); b=abs(old.fpr-new.fpr); c=abs(old.brier-new.brier)
    return DriftVector(a,b,c,a+b+c)

def classify(vector, *, threshold=Fraction(1,2)):
    return "DRIFT" if vector.l1 >= threshold else "STABLE"
