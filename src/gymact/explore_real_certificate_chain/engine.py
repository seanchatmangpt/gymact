from dataclasses import dataclass


@dataclass(frozen=True)
class EngineIdentity:
    name: str
    implementation: str
    model: str
    runtime: str

    def independent_of(self, other: "EngineIdentity") -> bool:
        return (
            self.implementation != other.implementation
            and self.model != other.model
            and self.runtime != other.runtime
        )
