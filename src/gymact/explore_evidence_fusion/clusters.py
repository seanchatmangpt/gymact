from .relation import relate, Relation
def correlated_clusters(observations, graph, independent_pairs=frozenset()):
    obs=list(observations); parent=list(range(len(obs)))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[b]=a
    for i in range(len(obs)):
        for j in range(i+1,len(obs)):
            key=frozenset((obs[i].evidence_id,obs[j].evidence_id))
            r=relate(obs[i],obs[j],graph,key in independent_pairs)
            if r in {Relation.SAME_EVIDENCE,Relation.CORRELATED}: union(i,j)
    buckets={}
    for i,o in enumerate(obs): buckets.setdefault(find(i),[]).append(o)
    return tuple(tuple(sorted(v,key=lambda x:x.evidence_id)) for v in sorted(buckets.values(),key=lambda v:min(x.evidence_id for x in v)))
