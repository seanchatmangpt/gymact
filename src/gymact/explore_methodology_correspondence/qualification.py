from dataclasses import dataclass
from .closure import Closure

@dataclass(frozen=True)
class Qualification:
    standing: str
    missing: tuple[str,...]

def qualify(closure: Closure, replay_ok: bool) -> Qualification:
    if not replay_ok: return Qualification('UNKNOWN',tuple(sorted(closure.missing)))
    if closure.complete: return Qualification('PARTIAL_ALIVE',())
    return Qualification('UNKNOWN',tuple(sorted(closure.missing)))
