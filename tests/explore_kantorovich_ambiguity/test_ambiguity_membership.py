from fractions import Fraction
import pytest
from gymact.explore_kantorovich_ambiguity import AmbiguitySet, FiniteMeasure, GroundMetric, Kind, Refused, chi_square

def test_wasserstein_and_chi_square_membership_are_distinct():
    pts=("a","b","c")
    x={"a":0,"b":1,"c":4}
    metric=GroundMetric.from_mapping(pts,{(a,b):abs(x[a]-x[b]) for a in pts for b in pts})
    center=FiniteMeasure.from_mapping({"a":2,"b":1,"c":1})
    candidate=FiniteMeasure.from_mapping({"a":1,"b":2,"c":1})
    w=AmbiguitySet.create(center,Kind.WASSERSTEIN1,Fraction(1,4),metric)
    c=AmbiguitySet.create(center,Kind.CHI_SQUARE,Fraction(1,2))
    assert w.contains(candidate)
    assert c.contains(candidate)
    assert w.distance(candidate)!=c.distance(candidate)

def test_chi_square_new_support_refuses():
    center=FiniteMeasure.from_mapping({"a":1})
    candidate=FiniteMeasure.from_mapping({"a":1,"b":1})
    with pytest.raises(Refused, match="CHI_SQUARE_POSITIVITY"):
        chi_square(candidate,center)
