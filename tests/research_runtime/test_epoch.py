from gymact.research_runtime.epoch import Epoch

def test_epoch_contract():
    assert Epoch(2,1).predecessor == 1
