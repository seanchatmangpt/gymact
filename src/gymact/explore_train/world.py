from dataclasses import dataclass

@dataclass
class CounterWorld:
    value: int = 0
    def observe(self) -> int: return self.value
    def construct(self, delta: int) -> dict[str, int]: return {"delta": delta}
    def simulate(self, intent: dict[str, int]) -> int: return self.value + intent["delta"]
