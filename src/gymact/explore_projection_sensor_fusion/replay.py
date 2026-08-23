from .receipt import Receipt
from .refusals import FusionRefused


def replay(receipt: Receipt, expected_digest: str) -> str:
    if receipt.actuation_performed:
        raise FusionRefused("REFUSED_REPORTED_ACTUATION")
    if receipt.digest != expected_digest:
        raise FusionRefused("REFUSED_RECEIPT_TAMPER")
    return "REPLAY_MATCH"
