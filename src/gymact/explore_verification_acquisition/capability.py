import hashlib
import json
from dataclasses import dataclass

from .subject import Refusal, Subject


@dataclass(frozen=True, slots=True)
class RailCapability:
    subject: Subject
    rail_id: str
    family: str
    domain: str
    scope: frozenset[str]
    cost_millis: int
    latency_millis: int

    def __post_init__(self) -> None:
        if not self.rail_id or not self.family or not self.domain or not self.scope:
            raise Refusal("REFUSED_INVALID_RAIL_CAPABILITY")
        if self.cost_millis <= 0 or self.latency_millis <= 0:
            raise Refusal("REFUSED_INVALID_RAIL_COST")

    @property
    def fingerprint(self) -> str:
        body = {
            "subject": self.subject.identity,
            "rail_id": self.rail_id,
            "family": self.family,
            "domain": self.domain,
            "scope": sorted(self.scope),
            "cost_millis": self.cost_millis,
            "latency_millis": self.latency_millis,
        }
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
