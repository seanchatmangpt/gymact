from datetime import datetime
from .cut import EvidenceCut
from .epoch import ProducerEpoch
from .observation import Observation

def admit_cut(cut: EvidenceCut, current: dict[str, ProducerEpoch], observations: tuple[Observation, ...], now: datetime) -> None:
    if not cut.is_active(now):
        raise ValueError("REFUSED_INACTIVE_CUT")
    selected=cut.epoch_map()
    if set(selected) != set(current):
        raise ValueError("REFUSED_INCOMPLETE_CURRENT_CUT")
    for repo, epoch in selected.items():
        cur=current[repo]
        if (epoch.generation, epoch.receipt, epoch.subject.sha) != (cur.generation, cur.receipt, cur.subject.sha):
            raise ValueError("REFUSED_STALE_CUT_EPOCH")
    observed={(o.epoch.subject.repo, o.epoch.generation) for o in observations}
    for repo, epoch in selected.items():
        if (repo, epoch.generation) not in observed:
            raise ValueError("REFUSED_MISSING_CUT_OBSERVATION")
