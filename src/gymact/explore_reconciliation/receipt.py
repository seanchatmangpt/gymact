from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .observation import Observation
from .subject import Subject


@dataclass(frozen=True, slots=True)
class Receipt:
    subject: str
    standing: str
    evidence: tuple[tuple[str, str, str], ...]
    actuation_performed: bool
    digest: str


def make_receipt(subject: Subject, standing: str, observations: tuple[Observation, ...]) -> Receipt:
    evidence = tuple(sorted((item.axis, item.outcome, item.source) for item in observations))
    body = {
        "schema": "gymact.explore-reconciliation/1",
        "subject": subject.identity,
        "standing": standing,
        "evidence": evidence,
        "actuation_performed": False,
    }
    digest = sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return Receipt(subject.identity, standing, evidence, False, digest)
