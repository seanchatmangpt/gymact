from dataclasses import dataclass
from .methodology import require_closure
from .receipt import Receipt
from .standing import Standing,combine
from .subject import Subject
@dataclass(frozen=True)
class Qualification:
    standing:Standing; receipt:Receipt|None
def qualify(subject:Subject,selector:str,mode:str,methodologies:frozenset[str],states:tuple[Standing,...])->Qualification:
    require_closure(methodologies)
    standing=combine(states)
    if standing is Standing.BUILD_BROKEN:return Qualification(standing,None)
    receipt=Receipt(subject.key,selector,mode,standing.value,False)
    return Qualification(standing,receipt)
