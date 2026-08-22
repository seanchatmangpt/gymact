from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeCandidate:
    name: str
    runner: Callable[[dict], dict]

    def run(self, payload: dict) -> dict:
        result = self.runner(dict(payload))
        if not isinstance(result, dict):
            raise TypeError("REFUSED_RUNTIME_RESULT_TYPE")
        return result
