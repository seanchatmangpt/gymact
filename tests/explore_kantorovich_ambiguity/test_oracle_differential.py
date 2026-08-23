from gymact.explore_kantorovich_ambiguity import FiniteMeasure, GroundMetric, compare

def test_flow_matches_independent_exhaustive_oracle():
    pts=("a","b","c")
    x={"a":0,"b":2,"c":5}
    metric=GroundMetric.from_mapping(pts,{(a,b):abs(x[a]-x[b]) for a in pts for b in pts})
    cases=[
        ({"a":1,"b":1},{"b":1,"c":1}),
        ({"a":2,"c":1},{"a":1,"b":1,"c":1}),
        ({"a":1,"b":2,"c":1},{"a":2,"b":1,"c":1}),
    ]
    for left,right in cases:
        d=compare(FiniteMeasure.from_mapping(left),FiniteMeasure.from_mapping(right),metric)
        assert d.gap==0
        assert d.primary==d.oracle
