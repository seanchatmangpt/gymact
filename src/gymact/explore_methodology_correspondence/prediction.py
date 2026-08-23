from collections import Counter

def predict_next(traces: tuple[tuple[str,...],...], prefix: tuple[str,...]) -> tuple[str,int]:
    c=Counter(t[len(prefix)] for t in traces if len(t)>len(prefix) and t[:len(prefix)]==prefix)
    if not c: raise ValueError('REFUSED_NO_PREDICTIVE_SUPPORT')
    activity,count=min(c.items(), key=lambda kv:(-kv[1],kv[0]))
    return activity,count
