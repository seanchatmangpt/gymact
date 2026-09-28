from gymact.research_runtime.health import ProviderHealth

def test_health_contract():
    assert ProviderHealth("a",False).healthy is False
