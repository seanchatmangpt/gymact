import pytest
from gymact.explore_consumer_binding.subject import Subject
def test_exact_subject_required():
    with pytest.raises(ValueError,match='REFUSED_INEXACT_SUBJECT'): Subject('o/r','abc')
