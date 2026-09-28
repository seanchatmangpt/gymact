from gymact.research_runtime.racap import PairedWorld

def test_racap_contract():
    assert PairedWorld("c","x",7).seed == 7
