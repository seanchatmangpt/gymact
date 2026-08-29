from __future__ import annotations

import re
from dataclasses import dataclass

from .refusals import FusionRefused

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class SensorIdentity:
    sensor_id: str
    family: str
    domain: str
    generation: int
    calibration_digest: str

    def __post_init__(self) -> None:
        if not self.sensor_id or not self.family or not self.domain or self.generation < 0:
            raise FusionRefused("REFUSED_INVALID_SENSOR_IDENTITY")
        if not _HEX64.fullmatch(self.calibration_digest):
            raise FusionRefused("REFUSED_INVALID_CALIBRATION_DIGEST")
