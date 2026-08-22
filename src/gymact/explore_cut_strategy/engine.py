from dataclasses import dataclass
from datetime import datetime
from .admission import admit_cut
from .authority import ActionClass, require
from .comparison import compare_strategies
from .cut import EvidenceCut
from .epoch import ProducerEpoch
from .observation import Observation, Outcome
from .receipt import QualificationReceipt
from .storage import select_store
from .strategies import CutStrategy, select_cut

@dataclass(frozen=True)
class Qualification:
    standing: str
    selected_cut: str
    strategy: CutStrategy
    receipt: QualificationReceipt
    comparisons: tuple

def qualify(*, subject: str, cuts: tuple[EvidenceCut,...], current: dict[str,ProducerEpoch], observations: tuple[Observation,...], now: datetime, strategy: CutStrategy, durable: bool=False, transactional: bool=False) -> Qualification:
    require(ActionClass.SELECT)
    cut=select_cut(cuts,current,strategy)
    admit_cut(cut,current,observations,now)
    outcomes=[o.outcome for o in observations if o.epoch.subject.repo in cut.epoch_map()]
    standing=("BUILD_BROKEN" if Outcome.FAIL in outcomes else "UNKNOWN" if any(o in (Outcome.PENDING,Outcome.UNKNOWN) for o in outcomes) else "UNSUPPORTED" if outcomes and all(o is Outcome.UNSUPPORTED for o in outcomes) else "PARTIAL_ALIVE")
    store=select_store(durable=durable,transactional=transactional)
    require(ActionClass.CONSTRUCT)
    receipt=QualificationReceipt(subject,cut.cut_id,strategy.value,store.kind.value,standing)
    return Qualification(standing,cut.cut_id,strategy,receipt,compare_strategies(cuts,current))
