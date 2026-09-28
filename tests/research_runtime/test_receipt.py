from gymact.research_runtime.receipt import RuntimeReceipt

def test_receipt_contract():
    assert RuntimeReceipt("s","e","ok").authority == "none"
