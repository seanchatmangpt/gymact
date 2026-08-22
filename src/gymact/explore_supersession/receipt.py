from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from .frontier import Frontier
from .subject import Refusal, Subject


@dataclass(frozen=True)
class Receipt:
    schema: str
    subject: str
    standing: str
    current: tuple[str, ...]
    historical: tuple[str, ...]
    actuation_performed: bool
    digest: str


def _body(subject: Subject, frontier: Frontier) -> dict[str, object]:
    return {
        "schema": "gymact.explore-supersession/1",
        "subject": subject.identity,
        "standing": frontier.standing,
        "current": tuple(sorted(row.evidence_id for row in frontier.current)),
        "historical": tuple(sorted(row.evidence_id for row in frontier.historical)),
        "actuation_performed": False,
    }


def make_receipt(subject: Subject, frontier: Frontier) -> Receipt:
    body = _body(subject, frontier)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return Receipt(**body, digest=hashlib.sha256(encoded).hexdigest())


def replay(receipt: Receipt, subject: Subject, frontier: Frontier) -> bool:
    if receipt.actuation_performed:
        raise Refusal("REFUSED_ACTUATION_IN_EXPLORE_RECEIPT")
    expected = make_receipt(subject, frontier)
    if asdict(receipt) != asdict(expected):
        raise Refusal("REFUSED_RECEIPT_MISMATCH")
    return True
