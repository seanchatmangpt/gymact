from dataclasses import dataclass
import re

from .refusal import Refused

_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class Subject:
    identity: str

    @classmethod
    def parse(cls, value: str) -> "Subject":
        if not _PATTERN.fullmatch(value):
            raise Refused("MALFORMED_SUBJECT", value)
        return cls(value)
