from .receipt import Receipt


def replay(receipt: Receipt, expected_digest: str) -> None:
    if receipt.actuation_performed or receipt.authority != "VERIFY":
        raise ValueError("RECEIPT_DRIFT")
    if receipt.digest != expected_digest:
        raise ValueError("RECEIPT_DRIFT")
