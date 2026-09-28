from gymact.research_runtime.circuit import Circuit

def test_circuit_contract():
    assert Circuit(3,3).failures >= Circuit(3,3).open_after
