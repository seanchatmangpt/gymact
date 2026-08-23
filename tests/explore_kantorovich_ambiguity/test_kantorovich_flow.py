from fractions import Fraction
from gymact.explore_kantorovich_ambiguity import FiniteMeasure, GroundMetric, wasserstein1

def line_metric():
    pts=("a","b","c")
    x={"a":0,"b":1,"c":3}
    return GroundMetric.from_mapping(pts,{(a,b):abs(x[a]-x[b]) for a in pts for b in pts})

def test_general_three_support_transport_conserves_mass():
    a=FiniteMeasure.from_mapping({"a":2,"b":1,"c":1})
    b=FiniteMeasure.from_mapping({"a":1,"b":1,"c":2})
    plan=wasserstein1(a,b,line_metric())
    assert plan.cost==Fraction(3,4)
    assert sum((v for _,_,v in plan.shipments),Fraction())==1
