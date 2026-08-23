from .receipt import SensitivityReceipt


def replay(receipt: SensitivityReceipt, expected_digest: str) -> bool:
    if receipt.actuation_performed:
        return False
    if receipt.action != "CONSTRUCT":
        return False
    return receipt.digest() == expected_digest
