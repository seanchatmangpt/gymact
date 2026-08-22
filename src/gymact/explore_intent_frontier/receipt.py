from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class QualificationReceipt:
    body: dict[str, object]
    digest: str


def manufacture(body: dict[str, object]) -> QualificationReceipt:
    payload = dict(body)
    payload["schema"] = "gymact.explore-intent-frontier/1"
    payload["actuation_performed"] = False
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return QualificationReceipt(payload, sha256(raw).hexdigest())


def replay(receipt: QualificationReceipt) -> bool:
    if receipt.body.get("actuation_performed") is not False:
        return False
    raw = json.dumps(receipt.body, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest() == receipt.digest
