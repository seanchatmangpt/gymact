from dataclasses import dataclass


@dataclass(frozen=True)
class FailureInjection:
    name: str
    trigger_at: int
    error: str

    def apply(self, index: int) -> None:
        if index == self.trigger_at:
            raise RuntimeError(self.error)
