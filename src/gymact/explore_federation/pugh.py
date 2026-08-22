def rank(matrix:dict[str,dict[str,float]], weights:dict[str,float])->tuple[tuple[str,float],...]:
    scored=[(cid,sum(vals.get(k,0.0)*w for k,w in weights.items())) for cid,vals in matrix.items()]
    return tuple(sorted(scored,key=lambda x:(-x[1],x[0])))
