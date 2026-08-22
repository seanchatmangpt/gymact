from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class Receipt:
    schema: str
    payload: dict[str, Any]
    digest: str


def issue(payload: dict[str, Any]) -> Receipt:
    bounded = dict(payload)
    bounded["actuation_performed"] = False
    raw = json.dumps(bounded, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    return Receipt("gymact.explore-epoch/1", bounded, digest)


def replay(receipt: Receipt) -> bool:
    if receipt.schema != "gymact.explore-epoch/1" or receipt.payload.get("actuation_performed") is not False:
        return False
    return issue({k: v for k, v in receipt.payload.items() if k != "actuation_performed"}).digest == receipt.digest
