from dataclasses import dataclass
from enum import StrEnum
import random


class Fault(StrEnum):
    SENSOR_DROPOUT = "SENSOR_DROPOUT"
    CORRELATED_ERROR = "CORRELATED_ERROR"
    STALE_CALIBRATION = "STALE_CALIBRATION"
    DELAYED_OBSERVATION = "DELAYED_OBSERVATION"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"


@dataclass(frozen=True, slots=True)
class FaultWorld:
    seed: int

    def choose(self, faults: tuple[Fault, ...]) -> Fault:
        return random.Random(self.seed).choice(faults)
