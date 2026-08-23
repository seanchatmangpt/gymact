from .errors import Refused
from .receipt import Receipt


def replay(receipt: Receipt, expected_digest: str) -> str:
    if receipt.authority != "SELECT":
        raise Refused("RECEIPT_AUTHORITY_DRIFT")
    if receipt.actuation_performed:
        raise Refused("REPORTED_AMBIENT_ACTUATION")
    if receipt.digest() != expected_digest:
        raise Refused("RECEIPT_DRIFT")
    return "REPLAY_MATCH"
