from gymact.research_runtime.queue import WorkQueue

def test_queue_contract():
    assert WorkQueue(("x",)).items == ("x",)
