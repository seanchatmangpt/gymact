from datetime import datetime
def admit(observations, subject, now:datetime):
    if now.tzinfo is None or now.utcoffset() is None: raise ValueError("REFUSED_NAIVE_ADMISSION_TIME")
    out=[]
    for o in observations:
        if o.observed_at>now: raise ValueError("REFUSED_FUTURE_EVIDENCE")
        if subject.repo not in o.source.producer and subject.repo not in o.evidence_id: raise ValueError("REFUSED_UNBOUND_EVIDENCE")
        out.append(o)
    ids=[o.evidence_id for o in out]
    if len(ids)!=len(set(ids)): raise ValueError("REFUSED_DUPLICATE_EVIDENCE_ID")
    return tuple(out)
