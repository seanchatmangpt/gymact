import inspect

from gymact.brce import BRCEBroker, BrokerRequest


def test_production_broker_exposes_execute_not_raw_act() -> None:
    assert hasattr(BRCEBroker, "execute")
    assert not hasattr(BRCEBroker, "act")
    parameters = inspect.signature(BrokerRequest).parameters
    assert "action" in parameters
    assert "prepared" in parameters
    assert "grant" in parameters
    assert "current_revision" in parameters
    assert "expected" in parameters
