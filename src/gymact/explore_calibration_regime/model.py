from dataclasses import dataclass
from fractions import Fraction
from .refusal import Refusal

@dataclass(frozen=True)
class CalibrationModel:
    source_id: str
    support: int
    tpr: Fraction
    fpr: Fraction
    brier: Fraction

def fit(source_id, trials, window, *, min_support=4):
    own=[t for t in trials if t.source_id==source_id and window.contains(t.observed_at)]
    if len(own)<min_support: raise Refusal("REFUSED_UNDER_SUPPORTED_WINDOW")
    pos=sum(t.actual_pass for t in own); neg=len(own)-pos
    tp=sum(t.actual_pass and t.predicted_pass for t in own)
    fp=sum((not t.actual_pass) and t.predicted_pass for t in own)
    err=sum(t.actual_pass != t.predicted_pass for t in own)
    return CalibrationModel(source_id,len(own),Fraction(tp+1,pos+2),Fraction(fp+1,neg+2),Fraction(err,len(own)))
