from dataclasses import dataclass
from .strategy import Strategy


@dataclass(frozen=True)
class Policy:
    name: str
    strategy: Strategy
    max_steps: int

    def __post_init__(self) -> None:
        if not self.name or self.max_steps <= 0:
            raise ValueError("REFUSED_INVALID_POLICY")


@dataclass(frozen=True)
class Planner:
    name: str


@dataclass(frozen=True)
class Role:
    name: str


@dataclass(frozen=True)
class Agent:
    name: str


@dataclass(frozen=True)
class Authority:
    reference: str
