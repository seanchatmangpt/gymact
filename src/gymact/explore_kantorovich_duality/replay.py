from __future__ import annotations

from .receipt import Receipt
from .refusal import refuse


def replay(receipt: Receipt, expected_digest: str) -> None:
    actual = receipt.digest()
    if actual != expected_digest:
        refuse("RECEIPT_DRIFT", f"expected {expected_digest} got {actual}")
