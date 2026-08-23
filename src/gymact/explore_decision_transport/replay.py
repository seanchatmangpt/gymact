from .receipt import Receipt
from .refusal import Refused


def replay(receipt: Receipt, expected_digest: str) -> str:
    if receipt.authority != "SELECT":
        raise Refused("AUTHORITY_DRIFT")
    if receipt.actuation_performed:
        raise Refused("ACTUATION_DRIFT")
    if receipt.digest() != expected_digest:
        raise Refused("RECEIPT_DRIFT")
    return "REPLAY_MATCH"
