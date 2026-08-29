from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from .errors import Refused
from .standing import Standing


@dataclass(frozen=True)
class Receipt:
    subject: str
    generation: int
    selected_relations: tuple[str, ...]
    standing: Standing
    authority: str = "SELECT"
    actuation_performed: bool = False

    def __post_init__(self) -> None:
        if self.actuation_performed:
            raise Refused("RECEIPT_REPORTS_AMBIENT_ACTUATION")

    def body(self) -> str:
        payload = asdict(self)
        payload["standing"] = self.standing.value
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return sha256(self.body().encode()).hexdigest()
