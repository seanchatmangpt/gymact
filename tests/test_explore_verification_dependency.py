import pytest

from gymact.explore_verification.dependency import topo


def test_dependency_order_and_cycle_refusal():
    assert topo({"a": set(), "b": {"a"}}) == ("a", "b")
    with pytest.raises(ValueError, match="REFUSED_DEPENDENCY_CYCLE"):
        topo({"a": {"b"}, "b": {"a"}})
