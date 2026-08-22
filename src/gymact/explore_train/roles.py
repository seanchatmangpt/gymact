from dataclasses import dataclass

@dataclass(frozen=True)
class Planner: name: str
@dataclass(frozen=True)
class Policy: name: str
@dataclass(frozen=True)
class Role: name: str
@dataclass(frozen=True)
class Agent: name: str
@dataclass(frozen=True)
class Authority: name: str

def assert_separated(*objects: object) -> bool:
    return len({type(o) for o in objects}) == len(objects)
