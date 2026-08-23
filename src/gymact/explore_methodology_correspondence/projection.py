from dataclasses import dataclass
from enum import StrEnum

class ProjectionKind(StrEnum):
    BEAM='BEAM'; WASM='WASM'; NIF='NIF'; REMOTE='REMOTE'; PLAN='PLAN'

@dataclass(frozen=True)
class Projection:
    kind: ProjectionKind
    semantic_digest: str
    executable: bool
    authority: str='CONSTRUCT'
    def admits_do(self) -> bool:
        return self.authority == 'DO'
