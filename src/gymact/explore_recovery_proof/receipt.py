from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

SCHEMA = "gymact.explore-recovery-proof/1"


@dataclass(frozen=True, slots=True)
class Receipt:
    body: dict[str, object]
    digest: str


def issue(body: dict[str, object]) -> Receipt:
    canonical = dict(body)
    canonical["schema"] = SCHEMA
    canonical["actuation_performed"] = False
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return Receipt(canonical, hashlib.sha256(raw).hexdigest())


def replay(receipt: Receipt) -> bool:
    if receipt.body.get("schema") != SCHEMA:
        return False
    if receipt.body.get("actuation_performed") is not False:
        return False
    raw = json.dumps(receipt.body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest() == receipt.digest
