from enum import StrEnum


class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    BUILD_BROKEN = "BUILD_BROKEN"


def derive(*, calibrated: bool, dependencies: list[Standing]) -> Standing:
    if Standing.BUILD_BROKEN in dependencies:
        return Standing.BUILD_BROKEN
    return Standing.PARTIAL_ALIVE if calibrated else Standing.UNKNOWN
