import pytest
from gymact.explore_consumer_binding.evidence import Evidence
from gymact.explore_consumer_binding.subject import Subject
def test_receipt_is_exact_digest():
    with pytest.raises(ValueError,match='REFUSED_INVALID_RECEIPT'): Evidence(Subject('o/r','a'*40),'x','s','FOCUSED','PASS')
