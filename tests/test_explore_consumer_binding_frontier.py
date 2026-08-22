import pytest
from gymact.explore_consumer_binding.evidence import Evidence
from gymact.explore_consumer_binding.frontier import resolve_frontier
from gymact.explore_consumer_binding.subject import Subject
def test_diverged_frontier_refuses():
    s=Subject('o/r','a'*40); a=Evidence(s,'b'*64,'v1','FOCUSED','PASS'); b=Evidence(s,'c'*64,'v1','FOCUSED','PASS')
    with pytest.raises(ValueError,match='REFUSED_DIVERGED_FRONTIER'): resolve_frontier([a,b])
