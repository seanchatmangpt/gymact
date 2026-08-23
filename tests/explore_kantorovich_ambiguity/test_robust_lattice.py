from fractions import Fraction
from gymact.explore_kantorovich_ambiguity import AmbiguitySet, FiniteMeasure, Kind, worst_case_lattice

def test_worst_case_retains_admitted_witness():
    center=FiniteMeasure.from_mapping({"safe":3,"bad":1})
    ambiguity=AmbiguitySet.create(center,Kind.TOTAL_VARIATION,Fraction(1,4))
    result=worst_case_lattice(ambiguity,{"safe":0,"bad":4},denominator=8)
    assert result.value>=center.expectation({"safe":0,"bad":4})
    assert ambiguity.contains(result.witness)
    assert result.evaluated>1
