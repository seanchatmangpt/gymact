from gymact.explore_dual_chain.receipt import manufacture, replay
from gymact.explore_dual_chain.runtime_projection import RuntimeProjection, correspond

def test_receipt_and_runtime_correspondence():
    receipt = manufacture({"authority": "VERIFY", "actuation_performed": False, "subject": "x"})
    assert replay(receipt)
    beam = RuntimeProjection("BEAM", "sem", "result")
    wasm = RuntimeProjection("WASM", "sem", "result")
    assert correspond(beam, wasm)
