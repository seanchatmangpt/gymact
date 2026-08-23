import pytest

from gymact.explore_ack_identity import Subject
from gymact.explore_ack_topology import DependencyGraph


def test_dependency_cycles_fail_closed():
    first = Subject("o/a", "a" * 40, "consumer")
    second = Subject("o/b", "b" * 40, "consumer")
    with pytest.raises(ValueError, match="REFUSED_DEPENDENCY_CYCLE"):
        DependencyGraph(
            (first, second),
            ((first.key, second.key), (second.key, first.key)),
        )
