from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimeResult:
    runtime: str
    value: Any


def execute(runtime: str, fn: Callable[[dict], Any], payload: dict) -> RuntimeResult:
    value = fn(dict(payload))
    return RuntimeResult(runtime, value)
