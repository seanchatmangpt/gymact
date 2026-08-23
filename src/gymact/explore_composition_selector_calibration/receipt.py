import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Receipt:
    subject: str
    selector: str
    mode: str
    standing: str
    actuation_performed: bool = False

    def body(self) -> dict[str, object]:
        return {
            "schema": "gymact.explore-composition-selector-calibration/1",
            "subject": self.subject,
            "selector": self.selector,
            "mode": self.mode,
            "standing": self.standing,
            "actuation_performed": self.actuation_performed,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.body(), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded).hexdigest()
