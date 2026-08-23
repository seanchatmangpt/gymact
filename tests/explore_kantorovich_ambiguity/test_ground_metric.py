import pytest
from gymact.explore_kantorovich_ambiguity import GroundMetric, Refused

def metric3():
    pts=("a","b","c")
    costs={(a,b):(0 if a==b else (1 if {a,b}!={"a","c"} else 2)) for a in pts for b in pts}
    return GroundMetric.from_mapping(pts,costs)

def test_metric_admits_triangle_space():
    m=metric3()
    assert m.cost("a","c")==2
    assert m.cost("a","b")+m.cost("b","c")==2

def test_triangle_violation_refuses():
    pts=("a","b","c")
    costs={(a,b):(0 if a==b else 1) for a in pts for b in pts}
    costs["a","c"]=costs["c","a"]=3
    with pytest.raises(Refused, match="TRIANGLE_INEQUALITY"):
        GroundMetric.from_mapping(pts,costs)
