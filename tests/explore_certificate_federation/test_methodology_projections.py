import pytest

from gymact.explore_certificate_federation.ocel import ObjectEvent, object_lifecycle
from gymact.explore_certificate_federation.powl import PowlModel, bounded_reachable
from gymact.explore_certificate_federation.refusal import FederationRefusal


def test_powl_and_object_lifecycle_projections() -> None:
    model = PowlModel(("a", "b", "c"), (("a", "b"), ("b", "a"), ("b", "c")))
    assert bounded_reachable(model, "a", "c", 2)
    assert not bounded_reachable(model, "a", "c", 1)
    events = (
        ObjectEvent("e1", "created", ("order-1",)),
        ObjectEvent("e2", "paid", ("order-1", "invoice-1")),
    )
    assert object_lifecycle(events, "order-1") == ("created", "paid")
    with pytest.raises(FederationRefusal, match="OBJECT_NOT_OBSERVED"):
        object_lifecycle(events, "missing")
