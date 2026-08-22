from .receipt import make


def verify(receipt: dict) -> bool:
    body = receipt.get("body", {})
    expected = make(body.get("payload", {}))
    if expected != receipt:
        raise ValueError("REFUSED_RECEIPT_MISMATCH")
    return True
