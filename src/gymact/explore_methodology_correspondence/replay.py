from .receipt import Receipt

def replay(receipt: Receipt, expected_digest: str) -> bool:
    return receipt.digest() == expected_digest and not receipt.actuation_performed
