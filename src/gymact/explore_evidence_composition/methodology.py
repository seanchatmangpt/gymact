from __future__ import annotations

from enum import StrEnum


class Methodology(StrEnum):
    DISCOVERY = "DISCOVERY"
    CONFORMANCE = "CONFORMANCE"
    SIMULATION = "SIMULATION"
    PREDICTION = "PREDICTION"
    OPTIMIZATION = "OPTIMIZATION"
    INTERVENTION = "INTERVENTION"
    MONITORING = "MONITORING"
    EVENT_CENTRIC = "EVENT_CENTRIC"
    OBJECT_CENTRIC = "OBJECT_CENTRIC"
    DECLARATIVE = "DECLARATIVE"
    PROCEDURAL = "PROCEDURAL"


REQUIRED = frozenset(Methodology)


def missing(observed: frozenset[Methodology]) -> frozenset[Methodology]:
    return REQUIRED - observed


def closed(observed: frozenset[Methodology]) -> bool:
    return not missing(observed)
