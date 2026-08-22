from collections import defaultdict
from .evidence import Evidence
def resolve_frontier(items:list[Evidence])->dict[str,Evidence]:
    groups=defaultdict(list)
    for e in items: groups[e.subject].append(e)
    out={}
    for subject,vals in groups.items():
        receipts={v.receipt for v in vals}
        if len(receipts)!=1: raise ValueError('REFUSED_DIVERGED_FRONTIER')
        out[f'{subject.repo}@{subject.sha}']=vals[0]
    return out
