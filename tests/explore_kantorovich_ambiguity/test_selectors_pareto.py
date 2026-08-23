from fractions import Fraction
from gymact.explore_kantorovich_ambiguity.pareto import frontier
from gymact.explore_kantorovich_ambiguity.selector import Candidate, Strategy, select

def test_selector_family_does_not_collapse_and_pareto_preserves_tradeoffs():
    a=Candidate("a",Fraction(1),Fraction(3),Fraction(1,5),2,Fraction())
    b=Candidate("b",Fraction(2),Fraction(2),Fraction(1,10),3,Fraction(1,10))
    c=Candidate("c",Fraction(4),Fraction(5),Fraction(1,2),1,Fraction(1))
    candidates=(a,b,c)
    assert select(candidates,Strategy.MIN_NOMINAL).identity=="a"
    assert select(candidates,Strategy.MIN_WORST).identity=="b"
    assert select(candidates,Strategy.MIN_RADIUS).identity=="b"
    assert {x.identity for x in frontier(candidates)}=={"a","b"}
